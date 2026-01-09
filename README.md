Un add on dans Home assistant pour scrapper les données de Consomation ILEO
Basé sur l'excellent travail de PBranly : https://github.com/pbranly/ILEO-home-assistant-scraper

C'est du partage de code, en etant ma premiere publication/ utilisation de Github

Les différences Vs le docker : 

## Installation
Comme un addon custom, besoin d'ajouter le depot pour pouvoir installer l'add-on
1/ Paramètres > Modules complémentaires > Boutique de modules complémentaires.
2/ Trois petits points (en haut à droite) > Dépôts (Repositories).
3/ Coller l'URL de votre dépôt GitHub.
4/ Votre add-on apparaîtra alors dans la liste !

## Configuration
Dans l'onglet configuration 4 options : 
* Les informations de connection au compte ILEO
* Le topic MQTT qui sera utilisé
* la fréquence de recuperation

  <img width="1320" height="696" alt="image" src="https://github.com/user-attachments/assets/52e3b58a-b6d6-4271-9dd5-9b297c81c36f" />
