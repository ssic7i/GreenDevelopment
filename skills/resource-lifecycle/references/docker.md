# Docker

Use `--platform docker`. Supported actions are `docker build`, `docker run/create`, and Compose `up/run/build/exec/logs/ps`. Use `--steps` for a build followed by its tests. The adapter namespaces tags/container names and labels resources with a random run ID, secret ownership token and resource kind before creation. It records the daemon identity and refuses cleanup if that identity changes.

```sh
python3 -B "$PLUGIN_ROOT/scripts/dev_resources.py" run \
  --session SESSION --task docker-check --repo /path/to/backend --platform docker \
  --steps '[["docker","build","-t","test-app","."],["docker","run","test-app","python","-m","unittest"]]'
```

For Compose, use a self-contained configuration in the source tree, such as `docker compose up --build --abort-on-container-exit --exit-code-from tests`. The runner renders normalized JSON and assigns owned service/network/volume names and labels. External resources, custom volume drivers, privileged/host namespaces, external write mounts and external build outputs are refused. Bind mounts must stay inside task work. Compose `run` must propagate the test service's status; detached `up` alone is not test evidence.

Cleanup rechecks labels via inspect before removing anything. It stops/removes owned containers and their anonymous volumes, then owned networks, named volumes and task-built images. Busy volumes/networks and externally tagged/in-use images remain blocked. Base/pulled images and shared Docker/BuildKit caches are retained. No prune, global compose down or force image/volume removal is used.

Standalone Docker options are intentionally constrained; unsupported options fail before execution. Use isolated Compose for named volumes/networks. User-selected external data and production services are not test fixtures.
