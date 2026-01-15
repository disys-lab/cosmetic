COSMeTICProver_IMAGE=anon2026dpeval/cosmeticprover:latest
COSMeTICStatsLogger_IMAGE=anon2026dpeval/cosmeticstatslogger:latest
PLATFORM=linux/amd64

.PHONY: all
all: build

.PHONY: build
build: build-prover build-statslogger

.PHONY: build-prover
build-prover:
	docker buildx build --file Dockerfile.pyslim.prover --platform $(PLATFORM) --tag $(COSMeTICProver_IMAGE) .

.PHONY: build-statslogger
build-statslogger:
	docker buildx build --file Dockerfile.pyslim.statslogger --platform $(PLATFORM) --tag $(COSMeTICStatsLogger_IMAGE) .
# .PHONY: push
# push: push-prover push-statslogger

# .PHONY: push-prover
# push-prover:
# 	docker push $(COSMeTICProver_IMAGE)

# .PHONY: push-statslogger
# push-statslogger:
# 	docker push $(COSMeTICStatsLogger_IMAGE)
# .PHONY: clean
# clean:
# 	-docker rmi $(zkpProver_IMAGE) || true
# 	-docker rmi $(STATS_LOGGER_IMAGE) || true