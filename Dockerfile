FROM spex.common:latest
USER root

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PATH="/opt/conda/bin:$PATH"

COPY ./microservices/ms-job-manager /app/services/app
COPY ./common /app/common

WORKDIR /app/services/app

RUN pipenv install --system --deploy --ignore-pipfile
RUN chmod +x ./install_r/install_r4.2.sh
RUN chmod +x ./install_r/install_libs.sh
RUN ./install_r/install_r4.2.sh
RUN ./install_r/install_libs.sh
RUN R -f ./install_r/install_libs.R
RUN chmod +x ./install_r/install_conda.sh
RUN ./install_r/install_conda.sh
RUN conda init bash
RUN pip install itsdangerous==2.0.1

CMD ["/bin/bash", "-c", "source /opt/conda/etc/profile.d/conda.sh && /usr/local/bin/python app.py"]
