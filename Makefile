IMAGE_NAME := youtube-auto-uploader
IMAGE_TAG := latest
RELEASE_NAME := youtube-uploader
HELM_CHART := helm/youtube-auto-uploader
KUBE_CTX := onprem-k3s
NAMESPACE := youtube-uploader
SERVER := yuta@172.16.0.51

CLIENT_SECRET ?= config/client_secret.json
TOKEN ?= config/token.json

.PHONY: build image-load secret install upgrade uninstall deploy logs status port-forward

# === ビルド & 取り込み ===

build:
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .

image-load: build
	docker save $(IMAGE_NAME):$(IMAGE_TAG) -o /tmp/$(IMAGE_NAME).tar
	scp /tmp/$(IMAGE_NAME).tar $(SERVER):/tmp/
	ssh $(SERVER) "sudo -n k3s ctr images import /tmp/$(IMAGE_NAME).tar && rm /tmp/$(IMAGE_NAME).tar"
	rm -f /tmp/$(IMAGE_NAME).tar

# === Secret作成 ===
# make secret CLIENT_SECRET=config/client_secret.json TOKEN=config/token.json

secret:
	kubectl --context $(KUBE_CTX) -n $(NAMESPACE) create secret generic $(RELEASE_NAME)-youtube-auth \
		--from-file=client_secret.json=$(CLIENT_SECRET) \
		--from-file=token.json=$(TOKEN) \
		--dry-run=client -o yaml | kubectl --context $(KUBE_CTX) -n $(NAMESPACE) apply -f -

# === Helm ===

install:
	helm upgrade --install $(RELEASE_NAME) $(HELM_CHART) --kube-context $(KUBE_CTX) -n $(NAMESPACE) --create-namespace

upgrade:
	helm upgrade $(RELEASE_NAME) $(HELM_CHART) --kube-context $(KUBE_CTX) -n $(NAMESPACE)

uninstall:
	helm uninstall $(RELEASE_NAME) --kube-context $(KUBE_CTX) -n $(NAMESPACE)

deploy: image-load upgrade

# === アクセス & 状態 ===

port-forward:
	kubectl --context $(KUBE_CTX) -n $(NAMESPACE) port-forward svc/$(RELEASE_NAME) 8081:8080

logs:
	kubectl --context $(KUBE_CTX) -n $(NAMESPACE) logs -f deploy/$(RELEASE_NAME)

status:
	kubectl --context $(KUBE_CTX) -n $(NAMESPACE) get pod,svc -l app=$(RELEASE_NAME)
