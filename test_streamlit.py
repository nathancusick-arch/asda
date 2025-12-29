import streamlit as st
import pandas as pd
import io

st.title("""Asda File Mapper""")

st.write("""
          1. Export the previous 2 weeks worth of data
          2. Drop the file in the below box, it should then give you the output file in your downloads
          3. Standard bits - Check data vs previous week, remove data already reported, paste over new data
          4. Copy and paste over values etc!!!
          5. Done.

          N.B. This currently works for alcohol, e-cigs, lottery, knives, cigs, fireworks, HD, C&C - New products will need mapping
          also. changing the question titles in Asda surveys will impact this. 
          """)

input_csv = st.file_uploader("whack it in 'ere")

def rearrange_and_merge_columns(input_csv, column_mapping):

    if input_csv is not None:
        df = pd.read_csv(input_csv)

        # ---------------------- REMOVE ABORTS ----------------------
        if "primary_result" in df.columns:
            df = df[df["primary_result"].astype(str).str.lower() != "abort"]

        # ---------------------- REMOVE AUDITS AFTER MOST RECENT FRIDAY ----------------------
        if 'date_of_visit' in df.columns:
            try:
                dates = pd.to_datetime(df['date_of_visit'].astype(str), errors='coerce', dayfirst=True)
                today = pd.Timestamp.today().normalize()
                weekday = today.weekday()
                days_since_friday = (weekday - 4) % 7
                most_recent_friday = today - pd.Timedelta(days=days_since_friday)
                df = df[dates <= most_recent_friday]
            except Exception as e:
                print('Date filter error:', e)

        # ---------------------- SORT AUDITS ----------------------
        if 'date_of_visit' in df.columns and 'time_of_visit' in df.columns and 'item_to_order' in df.columns:
            try:
                df['__sort_datetime'] = pd.to_datetime(
                    df['date_of_visit'].astype(str) + ' ' + df['time_of_visit'].astype(str),
                    errors='coerce',
                    dayfirst=True
                )
                df = df.sort_values(by=['item_to_order', '__sort_datetime'], ascending=[True, True])
                df = df.drop(columns=['__sort_datetime'])
            except Exception as e:
                print('Sorting error:', e)

        # ---------------------- CUSTOM MERGE LOGIC FOR FIREWORKS ----------------------
        col_allow = "Did the store colleague allow you to purchase the restricted item without providing ID?"
        col_handover = "Did the store colleague who served you at the fireworks cabinet, hand over the restricted item without providing ID?"
        fw_mask = df["item_to_order"] == "Fireworks - No ID"

        existing_fw_cols = [c for c in [col_allow, col_handover] if c in df.columns]
        df["merged_no_id_allow_handover"] = None

        if len(existing_fw_cols) == 2:
            df.loc[fw_mask, "merged_no_id_allow_handover"] = df.loc[fw_mask].apply(
                lambda row: row[col_allow] if row[col_allow] == "No" else row[col_handover],
                axis=1
            )
        elif len(existing_fw_cols) == 1:
            only_col = existing_fw_cols[0]
            df.loc[fw_mask, "merged_no_id_allow_handover"] = df.loc[fw_mask, only_col]
        else:
            pass

        if col_allow in df.columns:
            df.loc[fw_mask, col_allow] = ""

        # ---------------------- MERGE LOGIC FOR ASKED FOR ID ----------------------
        col_checkout_id = "Did the store colleague who served you at the checkout ask you for ID?"
        col_cabinet_id = "If you were able to complete your purchase of the restricted item, did the colleague who served you at the fireworks cabinet, ask you for ID?"

        existing_cols = [c for c in [col_checkout_id, col_cabinet_id] if c in df.columns]

        if existing_cols:
            df["merged_id_asked"] = df[existing_cols].apply(
                lambda row: "Yes" if ("Yes" in row.values) else "No",
                axis=1
            )
        else:
            df["merged_id_asked"] = pd.NA

        # ---------------------- BUILD OUTPUT ----------------------
        new_df = pd.DataFrame()

        for key, source in column_mapping.items():

            internal_col = key

            if isinstance(source, list):
                existing = [col for col in source if col in df.columns]
                if existing:
                    if len(existing) > 1:
                        new_df[internal_col] = df[existing].apply(
                            lambda row: next((val for val in row if pd.notnull(val) and val != ""), None),
                            axis=1
                        )
                    else:
                        new_df[internal_col] = df[existing[0]]
                else:
                    new_df[internal_col] = pd.NA
            else:
                new_df[internal_col] = df[source] if source in df.columns else pd.NA

        # ---------------------- RENAME BLANK COLUMNS AFTER BUILD ----------------------
        final_cols = []
        blank_export_map = {}
        blank_counter = 1

        for col in new_df.columns:
            if isinstance(col, str) and col.startswith("blank"):
                display = f"_blank_{blank_counter}"
                blank_export_map[display] = ""
                final_cols.append(display)
                blank_counter += 1
            else:
                final_cols.append(col)

        new_df.columns = final_cols

        export_df = new_df.rename(columns=blank_export_map)

        # ---------------------- EXPORT ----------------------
        output_csv = io.BytesIO()
        export_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
        st.write(new_df)
        output_csv.seek(0)

        st.download_button(
            label='Download CSV',
            data=output_csv.getvalue(),
            file_name='Asda Report Data.csv',
            mime='text/csv'
        )


column_mapping = {
    "order_internal_id": "order_internal_id",
    "client_name": "order_schedule_type",
    "internal_id": "internal_id",
    "blank1": "site_internal_id",
    "site_internal_id": "order_end_date",
    "order_end_date": "responsibility",
    "responsibility": "site_name",
    "site_name": "site_address_1",
    "site_address_1": "site_address_2",
    "site_address_2": "site_address_3",
    "site_address_3": "site_post_code",
    "site_post_code": "submitted_date",
    "submitted_date": "approval_date",
    "approval_date": "item_to_order",
    "item_to_order": "date_of_visit",
    "date_of_visit": "time_of_visit",
    "time_of_visit": None,
    "blank2": None,
    "primary_result": "primary_result",
    "secondary_result": None,
    "blank3": "site_code",
    "site_code": None,
    "blank4": None,
    "auditor_gender": "auditor_gender",
    "blank5": None,
    "auditor_name": "auditor_internal_id",
    "auditor_date_of_birth": "auditor_date_of_birth",
    "What type of alcohol did you try to purchase?": ["What type of alcohol did you purchase/try to purchase?", "What type of E-cigarette product did you purchase/attempt to purchase?", "What type of alcohol did you try to purchase?"],
    "Please give details of the product that you purchased:": ["Please give details of the alcohol purchased:", "Please give details of the lottery ticket you tried to purchase/purchased:", "Please give details of the cigarettes that you tried to purchase/purchased:", "Please give details of the alcohol that you tried to purchase:", "Please give details of the knife product that you tried to purchase/purchased:", "Please give details of the e-cig product that you tried to purchase:", "Please give details of the alcohol that you purchased:", "Please give details of the fireworks that you tried to purchase:"],
    "At which type of till was the purchase made?": "At which type of till was the purchase made?",
    "Did the staff member approach you to attend to your till?": "Did the staff member approach you to attend to your till?",
    "Did you make the purchase on your own?": "Did you make the purchase on your own?",
    "Did the store colleague who served you ask your age?": "Did the store colleague who served you ask your age?",
    "Did the store colleague who served you ask you for ID?": ["Did the driver ask for ID?", "Did the store colleague who served you ask you for ID?", "Did the store colleague who served you ask for your ID?", "merged_id_asked"],
    "Please confirm that you did not present any ID:": "Please confirm that you did not present any ID:",
    "Did the store colleague allow you to purchase the restricted item without providing ID?": ["Did the store colleague allow you to purchase the restricted item without providing ID?", "merged_no_id_allow_handover"],
    "Did the store colleague who served you make eye contact with you during the transaction?": ["Did the driver make eye contact with you during the interaction?", "Did the store colleague who served you make eye contact with you during the transaction?", "Did the person who served you make eye contact with you during the collection of your shopping?"],
    "When was eye contact first made?": "When was eye contact first made?",
    "What was the gender of the store colleague who served you?": ["What was the gender of the driver?", "What was the gender of the store colleague who served you?"],
    "What was the approximate age of the store colleague who served you?": "What was the approximate age of the store colleague who served you?",
    "Please input the approximate height of the server:": ["Please accurately describe the driver:", "Please input the approximate height of the server:", "Please accurately describe the store colleague who served you:"],
    "Please input the length of the server's hair:": "Please input the length of the server's hair:",
    "Please input the style of the server hair: ": "Please input the style of the server hair: ",
    "Please input the hair colour of the server:": "Please input the hair colour of the server:",
    "Please select whether the server had any of the following features:": "Please select whether the server had any of the following features:",
    "Please input their distinguishing characteristics:": "Please input their distinguishing characteristics:",
    "What was the name of the store colleague who served you?": "What was the name of the store colleague who served you?",
    "How many people were in the queue?": "How many people were in the queue?",
    "Were 'Challenge 25' notices visible at the till?": "Were 'Challenge 25' notices visible at the till?",
    "From the receipt, please enter the 4-digit ST code:": ["On the delivery receipt there is a list of order details, please record the 'Order No':", "From the receipt, please enter the 5-digit ST code:", "Enter the 'Order No.':"],
    "Please enter the 8-digit OP code:": "Please enter the 6-digit OP code:",
    "Please enter the 2-digit TE code:": "Please enter the 2-digit TE code:",
    "Please enter the 5-digit TR code:": "Please enter the 5-digit TR code:",
    "Please enter the time from the receipt:": "Please enter the time from the receipt:",
    "Please use this space to explain anything unusual about your visit or to clarify any detail of your report:": "Please use this space to explain anything unusual about your visit or to clarify any detail of your report:",
    "Please confirm in the space below whether or not you were asked for ID, and if so, whether the store colleague who served you allowed the transaction through without you presenting ID:": ["Please confirm below whether or not you were asked for ID:", "Please confirm whether or not you were asked for ID, and if so, at what point during the transaction ID was requested:"]
}

rearrange_and_merge_columns(input_csv, column_mapping)
