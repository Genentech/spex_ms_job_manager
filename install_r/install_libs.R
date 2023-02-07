for(package_name in c("pacman", "BiocManager")){
  if (!require(package_name, quietly = TRUE)) {
    install.packages(
      package_name,
      repos = "https://cran.rstudio.com/",
      force = TRUE,
      quiet = TRUE,
      INSTALL_opts = "--no-html"
    )
    message(paste(package_name, "package installed."))
  }
}

packages_to_check <- c("SingleCellExperiment", "gtools", "doParallel", "ggplot2", "dplyr")
not_installed <- packages_to_check[!packages_to_check %in% rownames(installed.packages())]
if(length(not_installed) > 0){
  BiocManager::install(not_installed, quiet = TRUE)
  message(paste(not_installed, collapse = ", "), " packages installed.")
}

not_installed <- c("ggplot2","dplyr", "tidyr")
not_installed <- not_installed[!not_installed %in% rownames(installed.packages())]
if(length(not_installed) > 0){
  pacman::p_install(not_installed,lib = .libPaths()[1],dependencies = TRUE, verify_installed = TRUE, quiet = TRUE)
}

packages_to_check <- c("FNN", "RANN", "RJSONIO")
not_installed <- packages_to_check[!packages_to_check %in% rownames(installed.packages())]

for (pkg in not_installed) {
  if (!require(pkg, quietly = TRUE)) {
    install.packages(pkg, repos = "https://cran.rstudio.com/", quiet = TRUE)
    message(paste(pkg, "package installed."))
  }
}

# spdep section

if (!require("spdep", quietly = TRUE)) {
  system("apt-get install -y libudunits2-dev libgdal-dev libproj-dev")
  install.packages("sf")
  install.packages("spdep", configure.args="--with-udunits2-include=/usr/include/udunits2")
  message("spdep package installed.")
}
