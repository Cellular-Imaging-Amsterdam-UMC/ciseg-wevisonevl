ARG MODELS_IMAGE=w_cisegwevisonevl-model-cache:local
FROM python:3.12-slim-bookworm AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends git libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu126 \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip install --no-cache-dir --no-deps "wevisone-vl @ git+https://github.com/Tencent/WeVisOne-VL.git@40f735b8daed437ece982db9718e9c9856f52a79" \
    && python -m pip check
COPY ciseg_wevisonevl/ ciseg_wevisonevl/
COPY wrapper.py config.yaml bilayers_cli.py LICENSE NOTICE.md version.txt ./
COPY tools/validate_container.py tools/validate_container.py
ENV CISEGWEVISONEVL_MODELS=/models HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/matplotlib
ENTRYPOINT ["python", "/app/wrapper.py"]

FROM ${MODELS_IMAGE} AS model_cache
FROM runtime AS final
COPY --from=model_cache /models/ /models/
RUN python /app/tools/validate_container.py --inventory-only
ARG VERSION=0.1.0
ARG VCS_REF=unknown
LABEL org.opencontainers.image.title="CISegWeVisOneVL" \
      org.opencontainers.image.description="Offline WeVisOne-VL-4B microscopy segmentation for BIOMERO; includes pinned model weights" \
      org.opencontainers.image.source="https://github.com/Cellular-Imaging-Amsterdam-UMC/ciseg-wevisonevl" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}"
