# Point Docker-compatible clients at rootless Podman socket when available
if not set -q DOCKER_HOST; and set -q XDG_RUNTIME_DIR; and test -S "$XDG_RUNTIME_DIR/podman/podman.sock"
    set -gx DOCKER_HOST "unix://$XDG_RUNTIME_DIR/podman/podman.sock"
end
