"""Interface Streamlit des cartes YAKO : employés et commerciaux."""

from __future__ import annotations

from io import BytesIO
from streamlit_paste_button import paste_image_button
import fitz
import streamlit as st
import re
from cards import ASSETS, Card, create_pdf
from imports import (COLUMNS, DEFAULT_ADDRESS, DEFAULT_COMPANY_EMAIL,
                     crop_qr, extract_screenshot, read_table)


st.set_page_config(page_title="Cartes YAKO AFRICA", page_icon="🟢", layout="wide")
st.markdown("""
<style>
.stApp {
    background-color: #000000;
    color: #ffffff;
}

.stApp p, .stApp label, .stApp span,
.stApp h1, .stApp h2, .stApp h3 {
    color: #ffffff;
}

div[data-baseweb="input"] input,
div[data-baseweb="textarea"] textarea {
    color: #ffffff !important;
    background-color: #000000 !important;
}

div[data-baseweb="select"] {
    color: #ffffff !important;
    background-color: #000000 !important;
}
</style>
""", unsafe_allow_html=True)
st.title("Cartes de visite YAKO AFRICA")
st.caption("85 × 55 mm · Employés avec QR code · Commerciaux sans QR code · PDF CMJN")

if "cards" not in st.session_state:
    st.session_state.cards = []


def example_cards() -> list[Card]:
    return [
        Card("Helena NIAMKE", "Directrice commercial adjointe",
             "+225 07 89 71 59 76", "+225 07 89 71 59 76",
             "helena.niamke@yakoafricassur.com", qr_png=(ASSETS / "qr_helena.png").read_bytes()),
        Card("Marie-Thérèse SAHOU", "Responsable Grands Comptes - Cluster Entreprises",
             "05 96 15 49 49", "05 96 15 49 49",
             "marie-therese.sahou@yakoafricassur.com", qr_png=(ASSETS / "qr_marie.png").read_bytes()),
        Card("Mamadou DOSSO", "Responsable Marketing et Communication",
             "+225 07 97 20 43 93", "+225 07 97 20 43 93",
             "mamadou.dosso@yakoafricassur.com", qr_png=(ASSETS / "qr_mamadou.png").read_bytes()),
    ]

def format_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)

    if digits.startswith("225") and len(digits) == 13:
        digits = digits[3:]

    if len(digits) != 10:
        raise ValueError(f"Numéro invalide : {value!r} (10 chiffres attendus).")

    return "+225 " + " ".join(digits[i:i + 2] for i in range(0, 10, 2))


def parse_pasted_people(text: str) -> list[dict]:
    # Une ligne vide sépare deux personnes.
    blocks = re.split(r"\n\s*\n", text.strip())
    people = []

    for number, block in enumerate(blocks, start=1):
        lines = [
    re.sub(
        r"^(?:nom(?: et pr[ée]nom)?|fonction|poste|t[ée]l[ée]phone|"
        r"mobile|second num[ée]ro|e-?mail|mail|adresse|lieu professionnel)"
        r"\s*:\s*",
        "",
        line.strip(),
        flags=re.IGNORECASE,
    ).strip()
    for line in block.splitlines()
    if line.strip()
]
        if len(lines) < 4:
            raise ValueError(
                f"Personne {number} : indique au moins le nom, "
                "la fonction, le téléphone et l'e-mail."
            )

        name, role = lines[0], lines[1]
        email_positions = [i for i, line in enumerate(lines) if "@" in line]
        if len(email_positions) != 1:
            raise ValueError(f"Personne {number} : un seul e-mail est attendu.")

        email_index = email_positions[0]
        phone_lines = lines[2:email_index]

        if len(phone_lines) not in (1, 2):
            raise ValueError(
                f"Personne {number} : place un ou deux numéros "
                "entre la fonction et l'e-mail."
            )

        if len(lines[email_index + 1:]) > 1:
            raise ValueError(
                f"Personne {number} : une seule ligne d'adresse est attendue après l'e-mail."
            )

        phone = format_phone(phone_lines[0])
        mobile = format_phone(phone_lines[1]) if len(phone_lines) == 2 else phone

        people.append({
            "name": name,
            "role": role,
            "phone": phone,
            "mobile": mobile,
            "email": lines[email_index],
            "address": lines[email_index + 1] if len(lines) > email_index + 1 else "",
        })

    return people

def add_card(kind: str, name: str, role: str, phone: str, mobile: str,
             email: str, address: str, company_email: str,
             qr: bytes | None, auto_qr: bool = False) -> None:
    if kind not in ("Employé", "Commercial"):
        raise ValueError("Choisis Employé ou Commercial.")
    if not all((name.strip(), role.strip(), phone.strip(), email.strip())):
        raise ValueError("Nom, fonction, téléphone et e-mail sont obligatoires.")
    if kind == "Employé" and qr is None and not auto_qr:
        raise ValueError("Ajoute le QR code de l'employé ou active sa génération automatique.")
    st.session_state.cards.append(Card(
        name=name.strip(), role=role.strip(), phone=phone.strip(),
        mobile=mobile.strip() or phone.strip(), email=email.strip(),
        address=address.strip(),
        company_email=company_email.strip() or DEFAULT_COMPANY_EMAIL,
        qr_png=qr if kind == "Employé" else None, kind=kind))


left, right = st.columns([1.1, .9], gap="large")
with left:
    tab_manual, tab_paste, tab_table, tab_image = st.tabs([
    "Saisie manuelle", "Copier-coller", "CSV / Excel", "Capture d'écran"
])

    with tab_paste:
        st.write(
            "Colle une information par ligne, dans l'ordre : nom, fonction, "
            "téléphone, mobile facultatif, e-mail, adresse facultative. "
            "Laisse une ligne vide entre deux personnes."
        )

        pasted_text = st.text_area(
            "Coordonnées à coller",
            height=280,
            placeholder=(
                "Aïcha KOUASSI\n"
                "Responsable commerciale\n"
                "0700000000\n"
                "aicha.kouassi@yakoafricassur.com\n"
                "Abidjan\n"
                "\n"
                "Jean KOUADIO\n"
                "Conseiller commercial\n"
                "+225 01 02 03 04 05\n"
                "0506070809\n"
                "jean.kouadio@yakoafricassur.com"
            ),
        )

        pasted_employee = st.checkbox(
            "Ce sont des employés",
            value=True,
            key="paste_employee",
        )

        pasted_qr_mode = "Générer automatiquement"
        pasted_qr_file = None

        if pasted_employee:
            pasted_qr_mode = st.radio(
                "QR code",
                ["Générer automatiquement", "Importer un QR code"],
                key="paste_qr_mode",
            )
            if pasted_qr_mode == "Importer un QR code":
                pasted_qr_file = st.file_uploader(
                    "Image du QR code",
                    type=["png", "jpg", "jpeg"],
                    key="paste_qr_file",
                )

        if st.button("Ajouter les cartes depuis le texte collé", type="primary"):
            try:
                people = parse_pasted_people(pasted_text)

                if pasted_employee and pasted_qr_mode == "Importer un QR code":
                    if len(people) != 1:
                        raise ValueError(
                            "Pour plusieurs employés, choisis la génération automatique : "
                            "chaque personne aura son propre QR code."
                        )
                    if pasted_qr_file is None:
                        raise ValueError("Importe l'image du QR code.")

                for person in people:
                    add_card(
                        "Employé" if pasted_employee else "Commercial",
                        person["name"],
                        person["role"],
                        person["phone"],
                        person["mobile"],
                        person["email"],
                        person["address"],
                        DEFAULT_COMPANY_EMAIL,
                        pasted_qr_file.getvalue() if pasted_qr_file else None,
                        auto_qr=pasted_employee and pasted_qr_mode == "Générer automatiquement",
                    )

                st.success(f"{len(people)} carte(s) ajoutée(s).")

            except ValueError as exc:
                st.error(str(exc))

    with tab_manual:
        with st.form("manual_form", clear_on_submit=True):
            kind = st.selectbox("Type de carte", ["Employé", "Commercial"])
            name = st.text_input("Nom et prénom *")
            role = st.text_input("Fonction *")
            c1, c2 = st.columns(2)
            phone = c1.text_input("Téléphone *")
            mobile = c2.text_input("Second numéro")
            email = st.text_input("E-mail personnel *")
            address = st.text_input("Lieu professionnel")
            company_email = st.text_input("E-mail général", value=DEFAULT_COMPANY_EMAIL)
            qr_file = st.file_uploader("QR code de l'employé (PNG, JPG, JPEG)",
                                      type=["png", "jpg", "jpeg"], key="manual_qr",
                                      help="Ignoré pour une carte Commercial.")
            auto_qr = st.checkbox("Générer un QR code vCard si aucun fichier n'est fourni")
            submitted = st.form_submit_button("Ajouter la carte", type="primary")
        if submitted:
            try:
                add_card(kind, name, role, phone, mobile, email, address,
                         company_email, qr_file.getvalue() if qr_file else None, auto_qr)
                st.success(f"Carte ajoutée : {name}")
            except ValueError as exc:
                st.error(str(exc))

    with tab_table:
        st.write("Une ligne par carte. Indique **Employé** ou **Commercial** dans `type`. Pour un employé, mets le nom de son image dans `qr_fichier` et téléverse les images ci-dessous.")
        template = ("type;nom;fonction;telephone;mobile;email;adresse;email_societe;qr_fichier\n"
                    "Employé;Aïcha KOUASSI;Responsable commerciale;+225 07 00 00 00 00;;"
                    "aicha.kouassi@yakoafricassur.com;Immeuble pacifique, Rue du commerce;"
                    "infos@yakoafricassur.com;aicha.png\n"
                    "Commercial;Jean KOUADIO;Conseiller commercial;+225 07 01 02 03 04;;"
                    "jean.kouadio@yakoafricassur.com;Immeuble pacifique, Rue du commerce;"
                    "infos@yakoafricassur.com;\n")
        st.download_button("Télécharger le modèle CSV", template.encode("utf-8-sig"),
                           "modele_cartes_yako.csv", "text/csv")
        sheet_file = st.file_uploader("Fichier CSV ou Excel", type=["csv", "xlsx"], key="batch")
        qr_files = st.file_uploader("Images des QR codes (plusieurs fichiers possibles)",
                                    type=["png", "jpg", "jpeg"], accept_multiple_files=True,
                                    key="batch_qrs")
        batch_auto = st.checkbox("Générer les QR codes manquants à partir des coordonnées", key="batch_auto")
        if sheet_file:
            try:
                table = read_table(sheet_file.getvalue(), sheet_file.name)
                st.caption("Vérifie et corrige les données ci-dessous avant de les ajouter.")
                edited = st.data_editor(table, hide_index=True, num_rows="dynamic",
                                        width="stretch", key="table_editor")
                if st.button("Ajouter les lignes vérifiées", type="primary"):
                    available = {file.name.lower(): file.getvalue() for file in qr_files}
                    prepared = []
                    for index, row in edited.fillna("").iterrows():
                        values = {column: str(row[column]).strip() for column in COLUMNS}
                        filename = values["qr_fichier"].lower()
                        if values["type"].casefold() in ("commercial", "commerciaux"):
                            category = "Commercial"
                        elif values["type"].casefold() in ("employé", "employe", "employés", "employes"):
                            category = "Employé"
                        else:
                            raise ValueError(f"Ligne {index+2} : type inconnu ({values['type']}).")
                        qr = available.get(filename) if filename else None
                        if category == "Employé" and filename and qr is None:
                            raise ValueError(f"Ligne {index+2} : image QR introuvable ({filename}).")
                        if category == "Employé" and qr is None and not batch_auto:
                            raise ValueError(f"Ligne {index+2} : QR requis ou génération automatique à activer.")
                        if not all(values[col] for col in ("nom", "fonction", "telephone", "email")):
                            raise ValueError(f"Ligne {index+2} : donnée obligatoire manquante.")
                        prepared.append(Card(values["nom"], values["fonction"], values["telephone"],
                                             values["mobile"] or values["telephone"], values["email"],
                                             values["adresse"],
                                             values["email_societe"] or DEFAULT_COMPANY_EMAIL,
                                             qr if category == "Employé" else None, category))
                    if not prepared:
                        raise ValueError("Aucune ligne à importer.")
                    create_pdf(prepared)  # Validate layout before adding the entire batch.
                    st.session_state.cards.extend(prepared)
                    st.success(f"{len(prepared)} carte(s) ajoutée(s).")
            except (ValueError, UnicodeError, ImportError) as exc:
                st.error(f"Import impossible : {exc}")

    with tab_image:
        st.write("Téléverse une capture de carte. L'application lit les textes, puis te laisse corriger chaque champ. Pour un employé, cadre le QR code visible sur la capture.")
        capture = st.file_uploader(
    "Importer une capture PNG, JPG ou JPEG",
    type=["png", "jpg", "jpeg"],
    key="capture",
)

pasted_capture = paste_image_button(
    "📋 Coller l'image copiée",
    key="paste_capture_button",
    errors="raise",
)
if pasted_capture.image_data is not None:
    buffer = BytesIO()
    pasted_capture.image_data.save(buffer, format="PNG")
    st.session_state["pasted_capture_bytes"] = buffer.getvalue()

capture_bytes = (
    capture.getvalue()
    if capture is not None
    else st.session_state.get("pasted_capture_bytes")
)

if capture_bytes and st.button("Effacer l'image collée"):
    st.session_state.pop("pasted_capture_bytes", None)
    st.rerun()

image_kind = st.selectbox(
    "Type de carte sur la capture",
    ["Employé", "Commercial"],
    key="image_kind",
)

if capture_bytes:
            st.image(capture_bytes, caption="Capture source", width="stretch")
            if image_kind == "Employé":
                st.caption("Cadrage du QR : pourcentage depuis le bord gauche et supérieur ; largeur relative à l'image.")
                x = st.slider("QR : position horizontale (%)", 0, 90, 5)
                y = st.slider("QR : position verticale (%)", 0, 90, 40)
                size = st.slider("QR : largeur (%)", 5, 60, 20)
                try:
                    qr_crop = crop_qr(capture_bytes, x, y, size)
                    st.image(qr_crop, caption="QR extrait à vérifier", width=130)
                except ValueError as exc:
                    qr_crop = None
                    st.warning(str(exc))
            else:
                qr_crop = None
            if st.button("Lire la capture et préparer la carte"):
                try:
                    draft = extract_screenshot(capture_bytes)
                    st.session_state.image_draft = {"kind": image_kind, "fields": draft,
                                                    "qr": qr_crop}
                    st.success("Texte extrait. Vérifie les champs avant l'ajout.")
                except (RuntimeError, OSError) as exc:
                    st.error(str(exc))
if "image_draft" in st.session_state:
            draft = st.session_state.image_draft
            st.info("Les captures peuvent comporter des erreurs de lecture : contrôle les numéros, l'e-mail et le QR.")
            with st.form("image_review_form"):
                d = draft["fields"]
                rn = st.text_input("Nom et prénom *", value=d["nom"], key="review_name")
                rr = st.text_input("Fonction *", value=d["fonction"], key="review_role")
                rp = st.text_input("Téléphone *", value=d["telephone"], key="review_phone")
                rm = st.text_input("Second numéro", value=d["mobile"], key="review_mobile")
                re = st.text_input("E-mail *", value=d["email"], key="review_email")
                ra = st.text_input("Lieu professionnel", value=d["adresse"], key="review_address")
                rc = st.text_input("E-mail général", value=d["email_societe"], key="review_company")
                rq = None
                rauto = False
                if draft["kind"] == "Employé":
                    review_qr_mode = st.radio(
                        "QR code de l'employé",
                        [
                            "Générer à partir de l'e-mail",
                            "Utiliser le QR extrait de la capture",
                            "Importer un autre QR code",
                        ],
                        key="review_qr_mode",
                    )

                    if review_qr_mode == "Importer un autre QR code":
                        rq = st.file_uploader(
                            "Image du QR code",
                            type=["png", "jpg", "jpeg"],
                            key="review_qr",
                        )

                    rauto = review_qr_mode == "Générer à partir de l'e-mail"
                reviewed = st.form_submit_button("Ajouter cette carte", type="primary")
            if reviewed:
                try:
                    if draft["kind"] == "Employé":
                        if review_qr_mode == "Importer un autre QR code":
                            if rq is None:
                                raise ValueError("Importe le QR code ou choisis sa génération.")
                            chosen_qr = rq.getvalue()
                        elif review_qr_mode == "Utiliser le QR extrait de la capture":
                            if draft["qr"] is None:
                                raise ValueError("Aucun QR n'a été extrait de la capture.")
                            chosen_qr = draft["qr"]
                        else:
                            chosen_qr = None
                    else:
                        chosen_qr = None

                    add_card(
                        draft["kind"], rn, rr, rp, rm, re, ra, rc,
                        chosen_qr, rauto,
                    )
                    del st.session_state.image_draft
                    st.success(f"Carte ajoutée : {rn}")
                except ValueError as exc:
                    st.error(str(exc))

with right:
    st.subheader("Cartes à produire")
    if st.button("Charger les 3 cartes du modèle", disabled=bool(st.session_state.cards)):
        st.session_state.cards = example_cards()
        st.rerun()
    for i, card in enumerate(st.session_state.cards):
        st.write(f"Diagnostic adresse de {card.name} : {card.address!r}")
        col_name, col_remove = st.columns([.82, .18])
        col_name.write(f"**{i+1}. {card.name}** · {card.kind} · {card.role}")
        if col_remove.button("Retirer", key=f"remove_{i}"):
            st.session_state.cards.pop(i)
            st.rerun()
    if st.session_state.cards:
        try:
            pdf_bytes = create_pdf(st.session_state.cards)
            noms_cartes = []
            for card in st.session_state.cards:
                dernier_mot = card.name.strip().split()[-1].upper()
                dernier_mot = re.sub(r'[<>:"/\\|?*]', "", dernier_mot)
                noms_cartes.append(dernier_mot)

            types = {card.kind for card in st.session_state.cards}
            if types == {"Employé"}:
                suffixe = "EMPLOYÉS"
            elif types == {"Commercial"}:
                suffixe = "COMMERCIAUX"
            else:
                suffixe = "EMPLOYÉS_ET_COMMERCIAUX" 

            nom_pdf = "_".join(noms_cartes) + f"_{suffixe}.pdf"
            st.download_button("Télécharger le PDF des cartes", pdf_bytes,
                               file_name=nom_pdf, mime="application/pdf",
                               type="primary")
            document = fitz.open(stream=pdf_bytes, filetype="pdf")
            st.caption(f"{len(st.session_state.cards)} personne(s) · {len(document)} faces PDF")
            for page in list(document)[:2]:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                st.image(pix.tobytes("png"), width="stretch")
        except (ValueError, RuntimeError, OSError) as exc:
            st.error(f"Impossible de créer le PDF : {exc}")
    else:
        st.info("Ajoute une carte manuellement, par tableau ou depuis une capture.")

st.caption("Logo, bras et icônes d'origine fournis · Poppins · couleurs CMJN")
