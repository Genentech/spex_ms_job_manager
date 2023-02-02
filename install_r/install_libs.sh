#!/bin/bash

echo "Updating system"
apt-get update
apt-get upgrade -y

echo "Installing GDAL and UDUNITS2"
apt-get -y install libudunits2-dev libgdal-dev
