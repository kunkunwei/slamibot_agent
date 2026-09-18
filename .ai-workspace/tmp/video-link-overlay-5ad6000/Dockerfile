FROM scout-nav:product-9eebfd5-arm64
LABEL org.opencontainers.image.title="Scout navigation video-link test overlay" \
      org.opencontainers.image.base.name="scout-nav:product-9eebfd5-arm64" \
      org.opencontainers.image.revision="5ad6000" \
      org.opencontainers.image.created="2026-09-04"
COPY capture.py /Scout_mini_navigation/install/lib/python3/dist-packages/fastapi_service/capture.py
RUN /opt/python-api/bin/pip3 install --no-cache-dir "Pillow>=10,<13"
ENV CAMERA_VIDEO_LINK_FPS=20 \
    CAMERA_VIDEO_LINK_MAX_WIDTH=480 \
    CAMERA_VIDEO_LINK_JPEG_QUALITY=40
