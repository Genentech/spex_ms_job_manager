#!/bin/bash

# Install dependencies
apt-get update
apt-get install -y libcurl4-openssl-dev libxml2-dev libssl-dev libpcre2-dev liblzma-dev gfortran libreadline-dev libx11-dev libjpeg-dev
apt-get install -y libudunits2-dev libproj-dev libgeos-dev

# Download and extract R
wget https://cran.r-project.org/src/base/R-4/R-4.2.2.tar.gz
tar -xf R-4.2.2.tar.gz
cd R-4.2.2

# Configure and make R
./configure --enable-R-shlib
make

# Install R to /usr/local/bin
make install

# Add R to PATH
echo 'PATH="/usr/local/bin:$PATH"' >> /etc/profile
source /etc/profile

# Check R version
R --version