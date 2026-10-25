# Recipe for the later Docker/BIOMERO validation phase; not yet built or published.
ARG MODELS_IMAGE=w_cisegwevisonevl-model-cache:local
FROM ${MODELS_IMAGE} AS model_cache
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt pyproject.toml ./
RUN python -m pip install --no-cache-dir torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu126 \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip install --no-cache-dir --no-deps "wevisone-vl @ git+https://github.com/Tencent/WeVisOne-VL.git@40f735b8daed437ece982db9718e9c9856f52a79"
COPY ciseg_wevisonevl/ ciseg_wevisonevl/
COPY wrapper.py config.yaml bilayers_cli.py LICENSE ./
COPY --from=model_cache /models/ /models/
ENV CISEGWEVISONEVL_MODELS=/models HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "/app/wrapper.py"]
