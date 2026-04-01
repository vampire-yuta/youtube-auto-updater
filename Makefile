IMAGE_NAME := youtube-auto-uploader
IMAGE_TAG := latest
RELEASE_NAME := youtube-uploader
HELM_CHART := helm/youtube-auto-uploader
KIND_CLUSTER := youtube-uploader

# === クラスタ ===

.PHONY: cluster-create
cluster-create:
	kind create cluster --name $(KIND_CLUSTER)

.PHONY: cluster-delete
cluster-delete:
	kind delete cluster --name $(KIND_CLUSTER)

# === ビルド & ロード ===

.PHONY: build
build:
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .

.PHONY: load
load:
	kind load docker-image $(IMAGE_NAME):$(IMAGE_TAG) --name $(KIND_CLUSTER)

# === Secret作成 ===
# 使い方: make secret CLIENT_SECRET=path/to/client_secret.json TOKEN=path/to/token.json

.PHONY: secret
secret:
	kubectl create secret generic $(RELEASE_NAME)-youtube-auth \
		--from-file=client_secret.json=$(CLIENT_SECRET) \
		--from-file=token.json=$(TOKEN) \
		--dry-run=client -o yaml | kubectl apply -f -

# === Helm ===

.PHONY: install
install:
	helm install $(RELEASE_NAME) $(HELM_CHART)

.PHONY: upgrade
upgrade:
	helm upgrade $(RELEASE_NAME) $(HELM_CHART)

.PHONY: uninstall
uninstall:
	helm uninstall $(RELEASE_NAME)

# === アクセス ===

.PHONY: port-forward
port-forward:
	kubectl port-forward svc/$(RELEASE_NAME) 8080:8080

# === 一括操作 ===

.PHONY: deploy
deploy: build load upgrade

.PHONY: setup
setup: cluster-create build load install
	@echo ""
	@echo "セットアップ完了。次のステップ:"
	@echo "  1. make secret CLIENT_SECRET=path/to/client_secret.json TOKEN=path/to/token.json"
	@echo "  2. make port-forward"
	@echo "  3. http://localhost:8080 にアクセス"

# === ログ & 状態確認 ===

.PHONY: logs
logs:
	kubectl logs -f deploy/$(RELEASE_NAME)

.PHONY: status
status:
	kubectl get pods -l app=$(RELEASE_NAME)

# === クリーンアップ ===

.PHONY: clean
clean: uninstall cluster-delete
