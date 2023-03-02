FROM spex.common:latest
USER root

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY ./microservices/ms-job-manager /app/services/app
COPY ./common /app/common

WORKDIR /app/services/app

RUN pipenv install --system --deploy --ignore-pipfile
RUN chmod +x ./install_r/install_r4.2.sh
RUN chmod +x ./install_r/install_libs.sh
RUN ./install_r/install_r4.2.sh
RUN ./install_r/install_libs.sh
RUN R -f ./install_r/install_libs.R

CMD ["python", "app.py"]
