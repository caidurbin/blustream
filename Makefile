# Sandcastle image name. Matches @ai-hero/sandcastle's defaultImageName(),
# which is `sandcastle:<repo-dir>` when docker() is called without an imageName
# (see .sandcastle/main.mts).
SANDCASTLE_IMAGE := sandcastle:bluestream
SANDCASTLE_DOCKERFILE := .sandcastle/Dockerfile

# Optional positional iteration count, e.g. `make sandcastle 5`. Make would
# otherwise treat the number as a second goal, so we pull anything that isn't
# one of our real targets out of MAKECMDGOALS and (further down) declare it as a
# no-op target. Plain `make sandcastle` leaves this empty and main.mts uses its
# built-in default.
SANDCASTLE_ITERATIONS := $(filter-out sandcastle sandcastle-rebuild,$(MAKECMDGOALS))

.PHONY: sandcastle sandcastle-rebuild

# Rebuild the sandcastle Docker image. The Dockerfile has no COPY/ADD (the repo
# is bind-mounted at runtime), so .sandcastle is used as the build context to
# avoid shipping .venv/node_modules/logs as context.
sandcastle-rebuild:
	docker build -t $(SANDCASTLE_IMAGE) -f $(SANDCASTLE_DOCKERFILE) .sandcastle

# Run the parallel planner/review loop. Rebuilds the image first so the run
# always uses the current Dockerfile. An optional positional integer (e.g.
# `make sandcastle 5`) overrides the loop's max iterations for this run via the
# environment; with no argument the variable is empty and main.mts defaults it.
sandcastle: sandcastle-rebuild
	SANDCASTLE_MAX_ITERATIONS=$(SANDCASTLE_ITERATIONS) npm run sandcastle

# Swallow the optional positional integer so Make doesn't fail with
# "No rule to make target '5'". This is scoped to the supplied value only (not a
# global `%:` catch-all), so typos in other goals still surface as errors.
ifneq ($(SANDCASTLE_ITERATIONS),)
.PHONY: $(SANDCASTLE_ITERATIONS)
$(SANDCASTLE_ITERATIONS):
	@:
endif
