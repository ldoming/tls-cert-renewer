FROM python:3.9.0a3-alpine3.10 as builder
RUN apk update && apk add --no-cache bash curl jq tini
RUN curl -o aws-iam-authenticator https://amazon-eks.s3-us-west-2.amazonaws.com/1.14.6/2019-08-22/bin/linux/amd64/aws-iam-authenticator \
    && chmod +x ./aws-iam-authenticator
RUN \
    kubectl_version=$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt) && \
    echo "Downloading kubectl $kubectl_version" && \
    curl -LO https://storage.googleapis.com/kubernetes-release/release/${kubectl_version}/bin/linux/amd64/kubectl && \
    chmod +x ./kubectl && \
    mv ./kubectl /usr/local/bin/kubectl

FROM python:3.9.0a3-alpine3.10
RUN pip install boto3 \
  pyyaml \
  kubernetes
COPY src /src
COPY --from=builder /aws-iam-authenticator /usr/local/bin/
COPY --from=builder /usr/local/bin/kubectl /usr/local/bin/
ENV PATH=$PATH:/src
WORKDIR /src