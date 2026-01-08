ARG BUILD_FROM=ghcr.io/home-assistant/base-python:3.11
FROM ${BUILD_FROM}

# Configuration de l'environnement
ENV LANG C.UTF-8

# ===============================
# Installation Chromium + Python + Dépendances
# ===============================
RUN apk update && apk add --no-cache \
    python3 \
    py3-pip \
    chromium \
    chromium-chromedriver \
    udev \
    ttf-freefont \
    harfbuzz \
    nss \
    freetype \
    cairo \
    cups-libs \
    dbus-libs \
    eudev-libs \
    libgcc \
    libstdc++ \
    libx11 \
    libxcomposite \
    libxcursor \
    libxdamage \
    libxi \
    libxrandr \
    libxrender \
    libjpeg-turbo \
    libpng \
    libdrm \
    mesa \
    mesa-egl \
    tzdata \
    bash

# ===============================
# Installation des librairies Python
# ===============================
COPY scraper/requirements.txt /requirements.txt
RUN pip3 install --no-cache-dir -r /requirements.txt --break-system-packages

# ===============================
# Copie des fichiers du scraper
# ===============================
COPY scraper/ /scraper/
WORKDIR /scraper/

# ===============================
# Script de démarrage principal
# ===============================
COPY run.sh /run.sh
RUN chmod +x /run.sh

# Variables d'environnement pour Selenium
ENV CHROME_BIN=/usr/bin/chromium-browser
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# --- CHANGEMENT MAJEUR ICI ---
# On supprime la création du service S6 (igrestart)
# On lance directement run.sh comme commande principale
CMD [ "/run.sh" ]