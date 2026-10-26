"""Disk-backed instance stitching; memory is bounded by one source tile."""
import sqlite3
import numpy as np
import zarr
from numcodecs import Blosc
from .streaming import blocks


def starts(length, size, overlap):
    if length <= size:
        return [0]
    values = list(range(0, length-size+1, size-overlap))
    if values[-1] != length-size:
        values.append(length-size)
    return values


def windows(shape, size, overlap):
    for y in starts(shape[0], size, overlap):
        for x in starts(shape[1], size, overlap):
            yield y, x, min(y+size, shape[0]), min(x+size, shape[1])


class DiskStitcher:
    def __init__(self, path, shape, match_threshold=.5, semantic=False):
        self.path = path
        self.shape = shape
        self.threshold = match_threshold
        self.semantic = semantic
        self.db = sqlite3.connect(str(path/'objects.sqlite'))
        self.db.execute('PRAGMA cache_size=-8192')
        self.db.execute('CREATE TABLE objects (id INTEGER PRIMARY KEY, parent INTEGER, area INTEGER DEFAULT 0, final INTEGER DEFAULT 0)')
        self.db.execute('INSERT INTO objects (id,parent) VALUES (0,0)')
        self.next_id = 1
        self.ambiguous = 0
        self.matches = 0
        group = zarr.open_group(str(path/'canvas.zarr'), mode='w')
        codec = Blosc(cname='zstd', clevel=3)
        self.labels = group.create_dataset('labels', shape=shape, chunks=(512,512), dtype='u4', compressor=codec)
        self.weights = group.create_dataset('ownership', shape=shape, chunks=(512,512), dtype='u2', compressor=codec)

    def root(self, label):
        label = int(label)
        root = label
        while True:
            parent = self.db.execute('SELECT parent FROM objects WHERE id=?', (root,)).fetchone()[0]
            if parent == root:
                break
            root = parent
        while label != root:
            parent = self.db.execute('SELECT parent FROM objects WHERE id=?', (label,)).fetchone()[0]
            self.db.execute('UPDATE objects SET parent=? WHERE id=?', (root,label))
            label = parent
        return root

    def canonical(self, data):
        ids, inverse = np.unique(data, return_inverse=True)
        mapped = np.asarray([self.root(i) for i in ids], np.uint32)
        return mapped[inverse].reshape(data.shape)

    def add(self, window, local):
        y,x,y1,x1 = window
        old = self.canonical(np.asarray(self.labels[y:y1,x:x1]))
        weights = np.asarray(self.weights[y:y1,x:x1])
        known = weights > 0
        ids = np.unique(local)
        ids = ids[ids > 0]
        if self.next_id+len(ids) > np.iinfo(np.uint32).max:
            raise OverflowError('Too many tile instances for uint32 labels')
        new = np.zeros_like(local, dtype=np.uint32)
        for label in ids:
            target = self.next_id
            self.next_id += 1
            self.db.execute('INSERT INTO objects(id,parent) VALUES (?,?)', (target,target))
            new[local == label] = target
        if self.semantic:
            # One semantic class per prompt; ownership still selects a single tile context.
            for label in np.unique(new[new > 0]):
                self.db.execute('UPDATE objects SET parent=1 WHERE id=?', (int(label),))
        elif np.any(known):
            paired = known & (old > 0) & (new > 0)
            pairs, intersections = np.unique(np.stack([old[paired],new[paired]],axis=1), axis=0, return_counts=True)
            old_ids, old_counts = np.unique(old[known & (old>0)], return_counts=True)
            new_ids, new_counts = np.unique(new[known & (new>0)], return_counts=True)
            old_areas = dict(zip(old_ids,old_counts)); new_areas = dict(zip(new_ids,new_counts))
            candidates = []
            for (a,b), intersection in zip(pairs,intersections):
                if intersection >= 8 and intersection/(old_areas[a]+new_areas[b]-intersection) >= self.threshold:
                    candidates.append((int(a),int(b)))
            for a,b in candidates:
                if sum(c==a for c,_ in candidates) == 1 and sum(d==b for _,d in candidates) == 1:
                    ra,rb = self.root(a),self.root(b)
                    if ra != rb:
                        self.db.execute('UPDATE objects SET parent=? WHERE id=?', (min(ra,rb),max(ra,rb)))
                        self.matches += 1
                else:
                    self.ambiguous += 1
        # Farthest from a tile edge wins; earlier tiles win exact ties, including background.
        h,w = local.shape
        distance = np.minimum(np.minimum(np.arange(h)+1,h-np.arange(h))[:,None],
                              np.minimum(np.arange(w)+1,w-np.arange(w))[None,:]).astype(np.uint16)
        owns = distance > weights
        old[owns] = new[owns]
        weights[owns] = distance[owns]
        self.labels[y:y1,x:x1] = old
        self.weights[y:y1,x:x1] = weights
        self.db.commit()

    def finish(self, target, time_index, min_area=0):
        # Count after ownership and equivalence resolution; filter complete objects, never tile fragments.
        for y,x,y1,x1 in blocks(self.shape):
            data = self.canonical(np.asarray(self.labels[y:y1,x:x1]))
            ids,counts = np.unique(data,return_counts=True)
            for label,count in zip(ids,counts):
                if label:
                    self.db.execute('UPDATE objects SET area=area+? WHERE id=?', (int(count),int(label)))
        self.db.commit()
        cursor = self.db.execute('SELECT id,area FROM objects WHERE id>0 AND area>=? AND area>0 ORDER BY id', (min_area,))
        count = 0
        foreground = 0
        for label,area in cursor:
            count += 1
            foreground += area
            self.db.execute('UPDATE objects SET final=? WHERE id=?', (1 if self.semantic else count,label))
        self.db.commit()
        for y,x,y1,x1 in blocks(self.shape):
            data = self.canonical(np.asarray(self.labels[y:y1,x:x1]))
            ids,inverse = np.unique(data,return_inverse=True)
            mapped = np.asarray([self.db.execute('SELECT final FROM objects WHERE id=?',(int(i),)).fetchone()[0] for i in ids],np.uint32)
            target[time_index,0,0,y:y1,x:x1] = mapped[inverse].reshape(data.shape)
        return (int(bool(count)) if self.semantic else count),foreground

    def close(self):
        self.db.close()
