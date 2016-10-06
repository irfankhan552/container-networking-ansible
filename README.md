# Demo setup for OpenShift + OpenContrail on AWS
Ansible provisioning for container networking solutions using OpenContrail

This repository contains provisioning instructions to install OpenContrail
as a network overlay for container based cluster management solutions. 

Forked from https://github.com/Juniper/container-networking-ansible which was built for testing, this repo is my copy for setting a small cloud lab and demo environment. I have made the changes necessary to install OpenShift Origin with OpenContrail on EC2 and removed the Jenkins testing. As time allows I will update this readme with instructions to deploy this for yourself.

<!---
The opencontrail playbook consists of the following:
  - filter_plugins/ip_filters.py
  - roles/opencontrail{,_facts,_provision}

The playbooks are designed to be addons to the existing ansible provisioning for kubernetes and openshift.

### Kubernetes

#### Network segmentation and access control
When opencontrail is used as the kubernetes network plugin, it defaults to isolate all pods according to `namespace` and a user defined tag. External traffic is restricted to services that are annotated with a ExternalIP address or have "type" set to "LoadBalancer". This causes the opencontrail public to allocate an address on the public network and assign it to all the pods in this service.

Services in the `kube-system` namespace are also available to all Pods, irrespective of the namespace of the pod. This is configured via the `cluster-service` option in /etc/kubernetes/network.conf. The cluster-service network is also connected to the underlay network where masters and nodes are present.

Pods are expected to communicate with the master via its ClusterIP address.

#### Deployment
The kubernetes ansible playbook at https://github.com/kubernetes/contrib.

- edit ansible/group_vars/all.yml
```
networking: opencontrail
```

- inventory file:
```
[opencontrail:children]
masters
nodes
gateways

[opencontrail:vars]
opencontrail_public_subnet=192.0.2.0/24
opencontrail_kube_release=1.1

```

- patch ansible/cluster.yml according to:
https://github.com/kubernetes/contrib/pull/261

- run the ansible/cluster.yml playbook (e.g. via ansible/setup.sh)

-->

### OpenShift

#### Network segmentation and access control

There are several differences in design from a plain-vanilla kubernetes cluster deployment and an openshift deployment:
- OpenShift expects all external traffic to be delivered through the router service. The openshift router pod is a TCP load-balancer (ha-proxy by default) that performs SSL termination and delivers traffic to the pods that implement the service.
- OpenShift pods (builder/deployer) have the nasty habbit of trying to reach the master through its infrastructure IP address (rather than using the ClusterIP).
- OpenShift STI builder pods expect to be able to access external git repositories as well as package repositories for popular languages (python, ruby, etc...).
- OpenShift builder pods use the docker daemon in the node and expect it to be able to talk to the docker-repository service running as a pod (in the overlay).
- Deployer pods expect to be able to pull images from the docker-repository into the node docker daemon.

* In current test scripts, we expect the builder pods to use an http proxy in order to fetch software packages. The builder pods are spawned in the namespace of the user `project`. To provide direct external access, one would need to do so for all pods currently. Future versions of the contrail-kubernetes plugin should support source-nat for outbound access to the public network. It is also possible to add a set of prefixes that contain the software and artifact repositories used by the builder to the global `cluster-service` network.
* All the traffic between underlay and overlay is expected to occur based on the `cluster-service` gateway configured for ```default:default```

#### Deployment Steps

- I recommend creating a t2.micro node running Linux CentOS 7 on AWS as your "starting-point" node. This way you'll be subscribed to CentOS 7 and find out your region, EC2 image ID which you'll need anyway below. Search the AWS Marketplace for "CentOS 7 (x86_64) with Updates HVM" to find the image. Download and copy your AWS keys to this node's ~/.ssh/ directory and install the AWS CLI. Fill in the <_blanks_>... 

```
sudo yum install -y wget
wget <_keys URL for your key.pem_>
mv <_keys file_> .ssh/<_key_>.pem
chmod 400 .ssh/<_key_>.pem
eval $(ssh-agent)
ssh-add .ssh/<_key_>.pem
curl "https://s3.amazonaws.com/aws-cli/awscli-bundle.zip" -o "awscli-bundle.zip"
sudo yum install -y unzip
unzip awscli-bundle.zip
sudo ./awscli-bundle/install -i /usr/local/aws -b /usr/local/bin/aws

```
- Configure the AWS CLI ('aws configure') with your AWS IAM access key, secret (get these from the AWS console) and region (get this from the AWS console as well - e.g. us-west-2). You can leave the output format set to none or text, whatever you prefer. I think the default JSON is more readable for a lot of commands. After you configure it, try it to check it works. There's all kinds of useful commands you'll find in its help.
```
aws configure
aws ec2 describe-instances
 ```
 
- In the output from the last command, you'll see your region in the domain names and you'll see ami-d440a6e7 or something like that which is your image ID that you'll need below.
- Now let's install some prerequisite tools ansible python-boto and pyOpenSSL. To yum these you'll have to download and install EPEL. Also check you're using Ansible 1.94, not 2+  
```
wget http://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm
sudo rpm -ivh epel-release-latest-7.noarch.rpm
sudo yum install -y ansible python-boto pyOpenSSL git python-pip
sudo pip install --upgrade jinja2
ansible --version
```
- You can remove everything in you just created in your home directory now if you like.
- Now git clone this repo into a new src directory

```
git clone https://github.com/jameskellynet/container-networking-ansible.git
```
- This should create the container-networking-ansible directory
- Edit the file container-networking-ansible/test/ec2-origin/group_vars/all.yml which now contains

```
aws_region: us-west-2
ec2_image: ami-d440a6e7
ssh_user: centos
aws_vpc_name: openshift-demo-vpc
aws_keys: jamesk-keys
```

- In your edits, setup your AWS region (in case it's different), desired AWS VPC name (will get created the first time we create the cluster), and the name of the AWS keys file (without the .pem extension ). Also if you want to create several concurrent clusters, there's a cluster_job variable you can increment here or overwrite with -e in the ansible-playbook command line. If you are using a different AWS region than us-west-2, the EC2 image variable here might change. Use the appropriate image ID for a CentOS 7 machine with kernel version matching 3.10: 
```
$ uname -r
3.10.0-229.14.1.el7.x86_64
```
- Finally let's kick off our Ansible playbook and get going. This sets up the VMs we will need in a cluster. A deployer and gateway node in a "public" subnet, and a master, node1 and node2 in the "private" subnet.
```
cd container-networking-ansible/test/ec2-origin/
ansible-playbook -i localhost playbook.yml --tags=cluster
```
- If you observe any error, it is likely at the end of the playbook (the task called "cluster | wait_for host" that waits 5 mins for the VMs to start). If that fails, it is just because AWS is, on rare occasion, slow to start up and initialize the VMs. Wait until all VMs are started and initialized successfully before proceeding (you can check with the EC2 cli or web console).
- That should have generated cluster.status1 (unless you changed the cluster_job variable in all.yml), an Ansible inventory file. Check it out.
- Later if/when you want to tear down this cluster, then you can run this... and afterward remove the inventory.cluster1 and cluster.status1 files.
```
ansible-playbook -i cluster.status1 clean.yml
```
- Assuming it all worked, move on to setup the nodes in your new cluster. Run from the same directory as above. Before you run it, check in your EC2 console that all status check have completed.
```
ansible-playbook -i cluster.status1 playbook.yml --tags=deployer-install,workspace
```
- Before logging into the deployer node, config your ssh with ForwardAgent=Yes. This is needed to login and then proceed to the nodes in the private subnet, and it is needed by the deployer-automate option below.
```
vi ~/.ssh/config
(edit the file)
i
ForwardAgent=Yes
:wq
(done editing the file)
chmod 400 ~/.ssh/config
```
- Open your cluster.status1 file and grab the name of the newly created and setup deployer node (see it under [deployer]) and ssh to it. Also note the IP of the master node for the next command (see it under [masters]).
```
ssh <_something_>.compute.amazonaws.com
```
- You should now be on the deployer node. Test that from here, you can ssh into the master node in the other subnet using its private IP.
```
ssh 10.<_something_>
```
- If you can get into the master node, you're good. You'll want to access this later to run "oc" commands (the openshift CLI). Close the connection to the master node.
- Now you're back on the deployer node. You can optionally close the connection to the deployer node and run this from the starting-point node to automate the rest which is quite lengthy (option a) - I no longer recommend this option a, because I've hit weird issues where I needed to rerun one of the commands that make up this uber job.
```
ansible-playbook -i cluster.status1 playbook.yml --tags=deployer-automate
``` 
-  _Alternatively_, (option b) from the deployer, kick off a few playbooks manually that are performed by Jenkins in the automated Juniper tests that I removed (why I added the step above). It's normal to see an error in the command below validating stage 2 (run it nevertheless), which is why there's a workaround playbook run after that. 
```
cd src/openshift-ansible/
ansible-playbook -i inventory/byo/hosts playbooks/byo/system-install.yml
ansible-playbook -i inventory/byo/hosts playbooks/byo/opencontrail.yml
python playbooks/byo/opencontrail_validate.py --stage 1 inventory/byo/hosts
ansible-playbook -i inventory/byo/hosts playbooks/byo/config.yml
python playbooks/byo/opencontrail_validate.py --stage 2 inventory/byo/hosts
ansible-playbook -i inventory/byo/hosts playbooks/byo/systemd_workaround.yml
python playbooks/byo/opencontrail_validate.py --stage 2 inventory/byo/hosts
ansible-playbook -i inventory/byo/hosts playbooks/byo/opencontrail_provision.yml
python playbooks/byo/opencontrail_validate.py --stage 3 inventory/byo/hosts
ansible-playbook -i inventory/byo/hosts playbooks/byo/openshift_provision.yml
python playbooks/byo/opencontrail_validate.py --stage 4 inventory/byo/hosts
ansible-playbook -i inventory/byo/hosts playbooks/byo/applications.yml
python playbooks/byo/opencontrail_validate.py --stage 5 inventory/byo/hosts
```

- If any step above should fail (for example sometimes there are connection issues), you can simply re-run the command.
- Whichever previous option you took, you are now ready to reach your OpenShift console over the web. You can use any kind of client-side proxy that you like. Here are instructions for the one that I used. First you'll need the Google Chrome browser installed. Open it and go to https://chrome.google.com/webstore/detail/proxy-switchysharp/dpplabbmogkhghncfbfdeeokoefdjegm. 
- (For the version shown in the video but has not been updated in 2 years)
New version is located at https://chrome.google.com/webstore/detail/proxy-switchyomega/padekgcemlokbadohgkifijomclgjgif
Install this Chrome Extension called Proxy SwitchySharp/Omega by clicking "+Add to Chrome" You should get a little globe in the top-right of the browser now and you can always click it to toggle on and off of your client-side proxy. If you right-click the globe icon and select options, you can configure it. Do that and create a new profile. In the HTTP port put 3128 (where Squid proxy is listening), and in the HTTP proxy field enter the public fully qualified domain name of your gateway node. You can retrieve that from the Public DNS field in the AWS EC2 web console or using the command below on your starting-point node. It will look like "ec2-52-33-14-187.us-west-2.compute.amazonaws.com".
```
aws ec2  describe-instances --filters "Name=tag:Name,Values=origin-gateway-1" | grep "PublicDnsName"
```
- Further, select the checkbox that says "Use the same proxy server for all protocols". Save. Finally, go to the Proxy SwitchySharp General tab and select the box "Quick Switch". Drag and drop into the "Cycled Profiles" the boxes saying Direct Connection and OpenShift. Save. Now you can close the chrome tab for the switcher extension. Just clicking the globe icon will switch between a direct connection (globe is grey) and a proxied connection (globe is blue).

- When you're ready, activate the proxy. This sends your Chrome web traffic to the gateway node on port 3128. There are squid.conf rules to allow traffic matching certain patterns and certain hosts. Squid will proxy any URL ending in ".cluster.local" or ".compute.internal" or anything destined to the origin-master node's private IP address. The master is running the OpenShift web console on port 8443. Give it a go. Using the private IP of your master node, type a URL into the browser like "https://10.0.32.25:8443" This should take you to the web console and you can now login. Similarly when we deploy the sample Rails app, you can go to its URL that OpenShift will assign ending in ".cluster.local".
- Login to the OpenShift console using username test and password c0ntrail123 (that's a zero for the o). You should see a screen like this:<br/><br/>
![alt text](https://github.com/jameskellynet/container-networking-ansible/blob/master/openshift-console.png "")
<br/><br/>
- If you click on test the test project you have setup to demo, you can start to build it. Click Browse > Builds. Then Start this application build.
- On the master node you can use the "oc help" command to explore openshift. "oc login" will allow you to login with the user test. If you logout and want to log back in as the system admin then do "oc login -u system:admin -n default"
- I've now included the OpenContrail GUI. It depends on the analytics collectors and api. Those and the web component are running on the master node. Ideally these would instead run inside of a Kubernetes pod, and I'll change that when the work is done and tested upstream in OpenContrail. For now, if you want to access the GUI, then follow the proxy instructions as above for the OpenShift GUI. Using the private IP of your master node, type a URL into the browser like "https://10.0.32.25:8143". Note the different port of 8143. This should take you to the OpenContrail web console and you can now login using username "admin" and password "contrail123". You'll notice that the only the networking and policy functionality is useful. That is because the vRouters and other components are not "hooked up" to the analytics collector (in other words this is the quick and dirty demo edition of getting the GUI working, not the ideal model).
- Demo video: https://www.youtube.com/watch?v=iMo54WUg6Kk <br/><br/>
[![Alt text](http://img.youtube.com/vi/iMo54WUg6Kk/0.jpg)](https://www.youtube.com/watch?v=iMo54WUg6Kk)


