import streamlit as st
import os
import random
import pandas as pd
from PIL import Image
import base64
from io import BytesIO
import xlsxwriter
import smtplib
import ssl
from email.message import EmailMessage

###########################
# Configuration Constants #
###########################
BASE_DIR = "QT_assessment"
IMAGE_DIR = os.path.join(BASE_DIR, "images")
DEPTHPRO_DIR = os.path.join(BASE_DIR, "depthpro")
ENDODAC_DIR = os.path.join(BASE_DIR, "endodac")

# Depth categories as subfolders
DEPTH_CATEGORIES = ["high", "mid", "low"]

# Output Excel file
RESULTS_FILENAME = "evaluation_results.xlsx"

# Email to send results (you can customize or parameterize this)
RESULTS_EMAIL = "francesco.mazola94@gmail.com"

#################################
# Utility: gather all file paths#
#################################
def collect_image_triplets():
    """
    Collect all (original, depthpro, endodac, depth_category, filename) entries.
    Return a list of tuples.
    """
    triplets = []
    for cat in DEPTH_CATEGORIES:
        cat_img_dir = os.path.join(IMAGE_DIR, cat)
        cat_dp_dir = os.path.join(DEPTHPRO_DIR, cat)
        cat_ed_dir = os.path.join(ENDODAC_DIR, cat)
        
        # list all filenames in images/<cat>
        files_in_cat = os.listdir(cat_img_dir)
        
        for f in files_in_cat:
            # Construct full paths
            img_path = os.path.join(cat_img_dir, f)
            dp_path  = os.path.join(cat_dp_dir, f)
            ed_path  = os.path.join(cat_ed_dir, f)
            
            if os.path.isfile(img_path) and os.path.isfile(dp_path) and os.path.isfile(ed_path):
                triplets.append((img_path, dp_path, ed_path, cat, f))
    
    return triplets

#############################
# Main Streamlit app layout #
#############################
def main():
    st.title("Endoscopy Depth Estimation - Qualitative Comparison")

    # -- 1) Rater name
    rater_name = st.text_input("Enter your name (or ID):", "")
    
    # If no name, prompt user to input it
    if not rater_name:
        st.warning("Please enter your name to begin.")
        st.stop()
    
    st.write("Please compare the original colonoscopy frame (left) with two depth estimations (right).")
    st.write("Select which of the two right images provides a better perceived depth representation.")
    
    # -- 2) Load or initialize session state
    if "triplets_list" not in st.session_state:
        # Collect all matching images
        all_triplets = collect_image_triplets()
        # Shuffle them once
        random.shuffle(all_triplets)
        st.session_state.triplets_list = all_triplets
        st.session_state.current_idx = 0
        st.session_state.responses = []  # to store (rater, filename, category, chosen_model)
    
    # If we've reached the end
    if st.session_state.current_idx >= len(st.session_state.triplets_list):
        st.write("You have completed all available images! Thank you for your time.")
        
        # -- Provide a button to finalize and send results
        if st.button("Finalize & Send Results via Email"):
            df = pd.DataFrame(st.session_state.responses,
                              columns=["rater_name", "filename", "category", "chosen_model"])
            # Save to Excel
            df.to_excel(RESULTS_FILENAME, index=False)
            
            st.success(f"Results saved to {RESULTS_FILENAME}")
            
            # -- Attempt to email results
            success = send_results_email(RESULTS_FILENAME)
            if success:
                st.success(f"Results were emailed to {RESULTS_EMAIL} successfully!")
            else:
                st.error("Could not send email. Check your email configuration.")
                
        st.stop()
    
    # -- 3) Display current sample
    img_path, dp_path, ed_path, cat, filename = st.session_state.triplets_list[st.session_state.current_idx]
    
    col1, col2 = st.columns([1,2])
    
    # Original on the left
    with col1:
        st.write(f"**Original Image** (file: {filename})")
        st.image(Image.open(img_path), use_column_width=True)
    
    # On the right, show the two depth estimation images in random order
    with col2:
        # Decide how to shuffle positions
        pos_order = ["A", "B"]
        random.shuffle(pos_order)
        
        # If pos_order[0] == "A" -> A=DepthPro, B=EndoDac, else swap
        if pos_order[0] == "A":
            modelA_path = dp_path
            modelB_path = ed_path
            modelA_label = "DepthPro"
            modelB_label = "EndoDac"
        else:
            modelA_path = ed_path
            modelB_path = dp_path
            modelA_label = "EndoDac"
            modelB_label = "DepthPro"
        
        st.write("**Compare Depth Maps**")
        
        colA, colB = st.columns(2)
        with colA:
            st.write("**Option A**")
            st.image(Image.open(modelA_path), use_column_width=True)
        with colB:
            st.write("**Option B**")
            st.image(Image.open(modelB_path), use_column_width=True)
        
        # Radio button to pick best
        chosen = st.radio(
            "Which depth estimation looks better?",
            options=["Option A", "Option B"],
            key=f"choice_{st.session_state.current_idx}"
        )
        
    # -- 4) On "Next" button click, store the response
    if st.button("Next Image"):
        if chosen == "Option A":
            chosen_model = modelA_label
        else:
            chosen_model = modelB_label
        
        st.session_state.responses.append([rater_name, filename, cat, chosen_model])
        st.session_state.current_idx += 1
        st.experimental_rerun()

###############################
# Optional: email the results #
###############################
def send_results_email(excel_filename):
    """
    Send the Excel file as an attachment to RESULTS_EMAIL.
    For real usage, you must configure your email credentials
    and possibly use a secure approach (Secrets Manager or env vars).
    """
    try:
        # Read the Excel file as bytes
        with open(excel_filename, "rb") as f:
            file_data = f.read()
        
        # Create email
        message = EmailMessage()
        message["Subject"] = "Colonoscopy Depth Evaluation Results"
        message["From"] = "your_sending_email@gmail.com"   # Replace with your own
        message["To"] = RESULTS_EMAIL
        message.set_content("Here are the latest evaluation results in the attached Excel file.")
        
        # Add attachment
        message.add_attachment(file_data,
                               maintype="application",
                               subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               filename=excel_filename)
        
        # Use your email credentials here
        smtp_server = "smtp.gmail.com"
        smtp_port = 465
        sender_email = "your_sending_email@gmail.com"
        sender_password = "YOUR_APP_PASSWORD"  # For Gmail, use app-specific password
        
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(sender_email, sender_password)
            server.send_message(message)
        
        return True
    except Exception as e:
        print("Error sending email:", e)
        return False


if __name__ == "__main__":
    main()
