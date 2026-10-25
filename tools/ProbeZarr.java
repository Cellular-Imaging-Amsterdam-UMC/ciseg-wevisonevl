import loci.formats.in.ZarrReader;
import loci.formats.services.OMEXMLService;
import loci.common.services.ServiceFactory;
import java.security.MessageDigest;

/** Read-only compatibility probe, run in the existing OMERO Server Java runtime. */
class ProbeZarr {
    public static void main(String[] args) throws Exception {
        loci.common.DebugTools.setRootLevel("ERROR");
        for (String path: args) {
            ZarrReader reader=new ZarrReader();
            reader.setFlattenedResolutions(false);
            reader.setMetadataStore(new ServiceFactory().getInstance(OMEXMLService.class).createOMEXMLMetadata());
            reader.setId(path);
            System.out.println("STORE\t"+path+"\tseries="+reader.getSeriesCount());
            for(int s=0;s<reader.getSeriesCount();s++) {
                reader.setSeries(s);
                for(int level=0;level<reader.getResolutionCount();level++) {
                    reader.setResolution(level);
                    int w=Math.min(17,reader.getSizeX()), h=Math.min(13,reader.getSizeY());
                    for(int t=0;t<reader.getSizeT();t++) for(int c=0;c<reader.getSizeC();c++) {
                        byte[] pixels=reader.openBytes(reader.getIndex(0,c,t),0,0,w,h);
                        byte[] digest=MessageDigest.getInstance("SHA-256").digest(pixels);
                        StringBuilder hex=new StringBuilder();
                        for(byte b:digest)hex.append(String.format("%02x",b));
                        System.out.println("PIXELS\tseries="+s+"\tlevel="+level+"\ttime="+t+"\tchannel="+c+"\tshape="+reader.getSizeX()+"x"+reader.getSizeY()+"\tbytes="+pixels.length+"\tsha256="+hex);
                    }
                }
            }
            reader.close();
        }
    }
}
