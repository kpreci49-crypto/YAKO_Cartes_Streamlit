# Cartes de visite YAKO AFRICA

Application Streamlit pour créer des cartes de visite de **85 × 55 mm**, avec un recto et un verso par personne, puis télécharger un seul PDF. Le modèle **Employé** comporte un QR code ; le modèle **Commercial** n'en comporte pas.

## Lancer l'application

```bash
python -m venv .venv
# Windows : .venv\Scripts\activate
# macOS/Linux : source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

La page s'ouvre normalement sur `http://localhost:8501`. Les données saisies et les fichiers QR restent dans la session Streamlit locale. Le PDF est généré en mémoire et téléchargé avec le bouton prévu.

## Utilisation

1. Choisir **Employé** ou **Commercial**, puis saisir le nom, la fonction, les numéros, l'e-mail et le lieu professionnel.
2. Pour un employé, téléverser son QR code PNG/JPG/JPEG. La case « Générer un QR code vCard » permet d'en créer un à partir des coordonnées si le fichier manque. Pour un commercial, le recto ne contient ni QR ni séparation verticale.
3. Autre méthode : importer un CSV ou XLSX. Une ligne représente une personne. Les colonnes `type`, `nom`, `fonction`, `telephone`, `email` sont essentielles ; `mobile`, `adresse`, `email_societe` et `qr_fichier` complètent les données. Pour chaque `qr_fichier`, téléverser l'image correspondante. Corriger le tableau affiché avant l'ajout.
4. Autre méthode : importer une capture PNG/JPG/JPEG de carte. Le texte est extrait automatiquement, les champs peuvent être corrigés, et le cadrage du QR peut être ajusté sur la capture ou remplacé par un fichier.
5. Contrôler l'aperçu, puis télécharger le PDF. Chaque personne donne deux pages consécutives : recto, verso.

Le bouton **Charger les 3 cartes du modèle** reprend Helena NIAMKE, Marie-Thérèse SAHOU et Mamadou DOSSO avec leurs QR codes fournis. Il est disponible quand la liste est vide.

La lecture des captures exige **Tesseract OCR** installé sur l'ordinateur (`tesseract --version`). Les importations CSV/XLSX, la saisie manuelle et le PDF fonctionnent sans Tesseract. L'OCR peut se tromper, notamment sur les numéros et les petites captures ; vérifier les champs et le cadrage du QR avant l'ajout.

## Couleurs et impression

- Fond : référence écran `#076633`, écrit en DeviceCMYK dans le PDF.
- Orange : référence écran `#F9B233`, écrit en DeviceCMYK pour le nom et uniquement le **A** de « Assureur » au verso.
- Format : 85 × 55 mm, sans fond perdu. Pour une découpe industrielle, demander à l'imprimeur le fond perdu et son profil ICC avant de modifier le format ou les valeurs CMJN.
- Le dessin du logo fourni est conservé. Une copie PNG avec transparence remplace uniquement son fond noir ; le fichier original reste dans `assets/`.
- La main provient du grand fichier `bras_design_hd.png`, alignée sur la nouvelle image de référence et rognée au coin inférieur droit. Les quatre icônes originales fournies (téléphone, mobile, lieu, enveloppe) sont intégrées sans redessin ; l'enveloppe apparaît sur les deux lignes d'e-mail.
- Les textes utilisent Poppins ; les fonctions sous les noms sont en Poppins Italic, sans gras.

Le rendu CMJN d'un écran dépend du lecteur PDF et du profil couleur de l'imprimeur. Les valeurs de `cards.py` ont été ajustées pour reproduire les références hexadécimales dans l'aperçu PDF utilisé pour ce projet.

## Fichiers

- `app.py` : interface Streamlit.
- `cards.py` : génération du PDF et des QR codes.
- `imports.py` : lecture CSV/XLSX et extraction assistée des captures.
- `assets/` : logo, main, source des icônes et trois QR codes du modèle.
- `fonts/` : polices Poppins embarquées et licence OFL pour garder la mise en page sur Windows, macOS et Linux.
