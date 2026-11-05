# MinIO no longer publishes container images, so build it from source (AGPLv3).
FROM golang:1.24-alpine AS build
RUN apk add --no-cache git
ARG MINIO_TAG=RELEASE.2025-10-15T17-29-55Z
ARG MC_TAG=RELEASE.2025-08-13T08-35-41Z
RUN git clone -q --depth 1 -b "$MINIO_TAG" https://github.com/minio/minio /src/minio \
 && cd /src/minio && CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o /out/minio .
RUN git clone -q --depth 1 -b "$MC_TAG" https://github.com/minio/mc /src/mc \
 && cd /src/mc && CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o /out/mc .

FROM alpine:3.20
COPY --from=build /out/ /usr/local/bin/
ENTRYPOINT ["minio"]
