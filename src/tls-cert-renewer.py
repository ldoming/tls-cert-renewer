#!/usr/bin/env python

import boto3
import argparse
import time
import yaml
import json
import logging
import sys
import os
import glob
import os.path as path
import subprocess
from kubernetes import client, config
from logging.handlers import RotatingFileHandler

# Setup the log handlers to stdout and file.
parent_path = path.dirname(path.realpath(__file__))
log = logging.getLogger('tls-cert-renewer')
log.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
    )
handler_stdout = logging.StreamHandler(sys.stdout)
handler_stdout.setLevel(logging.DEBUG)
handler_stdout.setFormatter(formatter)
log.addHandler(handler_stdout)
handler_file = RotatingFileHandler(
  '{}/tls-cert-renewer.log'.format(parent_path),
  mode='a',
  maxBytes=1048576,
  backupCount=9,
  encoding='UTF-8',
  delay=True
  )
handler_file.setLevel(logging.DEBUG)
handler_file.setFormatter(formatter)
log.addHandler(handler_file)

s3 = boto3.client('s3')

def download_dir(prefix, bucket, local='./', client=s3):
  """
  params:
  - prefix: pattern to match in s3
  - local: local path to folder in which to place files
  - bucket: s3 bucket with target contents
  - client: initialized s3 client object
  """
  log.info('Downloading certificates!')
  try:
    keys = []
    dirs = []
    next_token = ''
    base_kwargs = {
      'Bucket':bucket,
      'Prefix':prefix,
    }
    parent_directory = ''
    while next_token is not None:
      kwargs = base_kwargs.copy()
      if next_token != '':
        kwargs.update({'ContinuationToken': next_token})
      results = client.list_objects_v2(**kwargs)
      contents = results.get('Contents')
      for i in contents:
        k = i.get('Key')
        if k[-1] != '/':
          keys.append(k)
        else:
          dirs.append(k)
        next_token = results.get('NextContinuationToken')
    for d in dirs:
      dest_pathname = os.path.join(local, d)
      if not os.path.exists(os.path.dirname(dest_pathname)):
        os.makedirs(os.path.dirname(dest_pathname))
      parent_directory = dest_pathname
    for k in keys:
      dest_pathname = os.path.join(local, k)
      if not os.path.exists(os.path.dirname(dest_pathname)):
        os.makedirs(os.path.dirname(dest_pathname))
      log.info("Downloading {}".format(k))
      client.download_file(bucket, k, dest_pathname)
    log.info('Certificates downloaded successfully!')
  except:
    log.error('Error downloading the certificate!')


def list_secret_for_all_namespaces():
  log.info('Gathering all tls secrets!')
  v1 = client.CoreV1Api()
  pretty = True

  try:
    api_response = v1.list_secret_for_all_namespaces(pretty=pretty, label_selector="tls-cert-renewer-enabled=true").to_dict()
    return api_response
  except ApiException as e:
    log.error("Exception when calling CoreV1Api->read_namespaced_config_map: %s\n" % e)

def delete_namespaced_secret(name, namespace):
  log.info('Deleting secret {} in namespace {}!'.format(name, namespace))
  v1 = client.CoreV1Api()
  try:
    api_response = v1.delete_namespaced_secret(name, namespace).to_dict()
    if api_response['status'] == "Success":
      log.info('Secret deleted successfully!')
      return True
    return False
  except ApiException as e:
    log.error("Exception when calling CoreV1Api->read_namespaced_config_map: %s\n" % e)

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--sleep_time', default=86400, help='Time interval to refresh user mappings. Default 1 day')
  parser.add_argument('--bucket_name', required=True, help='S3 bucket name')
  parser.add_argument('--prefix', required=True, help='Folder which the certificate was placed')
  args = parser.parse_args()

  log.info('Executing iam-eks-group-mapper application!')
  try:
    log.info("Trying in cluster API connection")
    config.load_incluster_config()
    log.info('Python client connected successfully!')
  except:
    log.warning('Unable to connect though incluster connection!')
    try:
      log.info("Trying in kubeconfig API connection")
      config.load_kube_config()
      log.info('Python client connected successfully!')
    except:
      log.error("Unable to connect to API")

  sleepTime = int(args.sleep_time) # default: 1 day
  bucket_name = args.bucket_name
  prefix = args.prefix
  secrets = list_secret_for_all_namespaces()
  while True:
    for secret in secrets['items']:
      parent_domain = secret['metadata']['labels']['tls-cert-renewer-parent-domain']
      secret_name = secret['metadata']['name']
      secret_namespace = secret['metadata']['namespace']
      new_prefix = "{}/{}".format(prefix, parent_domain)
      download_dir(new_prefix, bucket_name)
      if delete_namespaced_secret(secret_name, secret_namespace):
        pwd = os.path.dirname(os.path.realpath(__file__))
        certificate_dir = "{}/{}".format(pwd, new_prefix)
        os.chdir(certificate_dir)
        certificate = "{}/{}".format(certificate_dir, glob.glob("*.cer")[0])
        certificate_key = "{}/{}".format(certificate_dir, glob.glob("*.key")[0])
        os.chdir(pwd)

        FNULL = open(os.devnull, 'w')
        log.info('Creating new tls secret {}!'.format(secret_name))
        command = ['kubectl', 'create', 'secret', 'tls', secret_name, '-n', secret_namespace, '--cert', certificate, '--key', certificate_key]
        retval = subprocess.call(command, stdout=FNULL, stderr=subprocess.STDOUT)
        if retval >= 2:
            log.critical("Error creating certificate with return value of {}.".format(retval))
        else:
          log.info('New tls secret {} successfully created!'.format(secret_name))

        log.info('Patch tls secret {} with labels!'.format(secret_name))
        patch = {"metadata": {"labels": {"tls-cert-renewer-enabled":"true", "tls-cert-renewer-parent-domain":parent_domain}}}
        patch = json.dumps(patch) 
        command = ['kubectl', 'patch', 'secret', secret_name, '-n', secret_namespace, '--patch', patch]
        retval = subprocess.call(command, stdout=FNULL, stderr=subprocess.STDOUT)
        if retval >= 2:
            log.critical("Error patch certificate with return value of {}.".format(retval))
        else:
          log.info('Patch tls secret {} successfully executed!'.format(secret_name))
    log.info('Sleeping for {} seconds'.format(sleepTime))
    time.sleep(sleepTime)

if __name__ == '__main__':
  main()