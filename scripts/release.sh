#!/usr/bin/env bash
# Build the production image for the VM (linux/amd64) and push it to the
# private registry, tagged :latest and :<git short sha>.
#
#   make release            # or: scripts/release.sh
#   REGISTRY=... scripts/release.sh
set -euo pipefail

REGISTRY="${REGISTRY:-registry.steveperkins.com}"
IMAGE="$REGISTRY/innesto"
SHA="$(git -C "$(dirname "$0")/.." rev-parse --short HEAD)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ -n "$(git -C "$ROOT" status --porcelain)" ]; then
  echo "warning: working tree has uncommitted changes; image tag $SHA will not match its contents exactly" >&2
fi

# docker login status: the config lists authenticated registries.
if ! docker login "$REGISTRY" --get-login >/dev/null 2>&1 \
   && ! grep -q "\"$REGISTRY\"" "${DOCKER_CONFIG:-$HOME/.docker}/config.json" 2>/dev/null; then
  echo "Not logged in to $REGISTRY. Run:  docker login $REGISTRY" >&2
  exit 1
fi

docker buildx inspect innesto-builder >/dev/null 2>&1 || docker buildx create --name innesto-builder --use >/dev/null
docker buildx use innesto-builder

echo "Building $IMAGE:$SHA for linux/amd64 and pushing ..."
docker buildx build --platform linux/amd64 \
  -t "$IMAGE:latest" -t "$IMAGE:$SHA" \
  --push "$ROOT"

cat <<MSG

Pushed $IMAGE:latest and $IMAGE:$SHA

On the VM:
  cd ~/docker && docker compose pull innesto && docker compose up -d innesto
  docker compose logs -f innesto      # first start fetches translation models

Roll back:
  edit docker-compose.yml to image: $IMAGE:<previous sha>, then docker compose up -d innesto
MSG
