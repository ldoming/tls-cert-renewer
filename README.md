# tls-cert-renewer

This application is used to auto renew kubernetes ingress tls certificate.

### Note:
Secrets must contain the following metadata labels
```yaml
metadata:
  labels:
    tls-cert-renewer-enabled: 'true'
    tls-cert-renewer-parent-domain: <REPLACE>
```

## Setting up in your environment:
1) Create a new IAM User with an S3 download policy
2) Replace the ACCESS_KEY_ID environment variable in `kubernetes/deployment.yaml` with your new generated user's access key id
3) Replace the `awsKey:` variable in `deployment/secret.yaml` with the base64 contents of your generated user's secret access key
```bash
$ echo -n "secretkey" | base64
```
4) Update the `AWS_REGION` environment variable in `kubernetes/deployment.yaml` if you aren't running in `us-west-2` with your EKS cluster
5) Edit the `kubernetes/deployment.yaml` `command:` with following arguments

| Symbol | Default | Description
| --- | --- | ---
| `--bucket_name` | `Required` | Bucket Name
| `--prefix` | `Required` | Folder name where the certificate is located
| `--sleep_time` | `86400` | Time for the next execution


6) Finally:
```bash
$ kubectl apply -f kubernetes/
```

## Have suggestions or want to contribute?
Raise a PR or file an issue, I'd love to help!
