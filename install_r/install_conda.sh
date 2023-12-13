#!/bin/bash

echo "Updating system"
apt-get update
apt-get upgrade -y

echo "Downloading and Installing Anaconda"
wget https://repo.anaconda.com/archive/Anaconda3-2023.03-Linux-x86_64.sh
bash Anaconda3-2023.03-Linux-x86_64.sh -b -p /opt/conda
rm Anaconda3-2023.03-Linux-x86_64.sh

echo "Setting up Anaconda"
source /opt/conda/etc/profile.d/conda.sh

echo "Configuring Conda channels"
conda config --add channels defaults
conda config --add channels bioconda
conda config --add channels conda-forge
conda config --set channel_priority strict
