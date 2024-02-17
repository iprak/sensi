FROM ghcr.io/iprak/custom-integration-image:main

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

WORKDIR /workspaces

RUN echo "Installing components from requirements_component.txt"
RUN if [test -e requirements_component.txt]; then \
    pip3 install -r requirements_component.txt --use-deprecated=legacy-resolver; \
    fi

# Set the default shell to bash instead of sh
ENV SHELL /bin/bash
