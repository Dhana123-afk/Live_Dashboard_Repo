import gspread
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from google.oauth2.service_account import Credentials
import plotly.express as px
import plotly.graph_objects as go
# =========================
# CONFIG
# =========================
SERVICE_ACCOUNT_FILE = "credentials.json"
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NQSCTnd-YkdOGvWmdKj6tvwiezJUBe3lOG6WmqDL72U/edit?gid=501579247#gid=501579247"
ASANA_SHEET_URL = "https://docs.google.com/spreadsheets/d/19LEVmTAH2mv0NtIp89OdIZM9M1IRtKXFgb5UrJviZpo/edit?gid=108310761#gid=108310761"
META_WORKSHEET_NAME = "MetaAds_History"
GA4_WORKSHEET_NAME = "GA4_Historical_Data"
MAILERLITE_WORKSHEET_NAME = "MailerLite_History"
MAILERLITE_CAMPAIGNS_WORKSHEET = "MailerLite_Campaigns"
MAILERLITE_SUBSCRIBERS_WORKSHEET = "MailerLite_Subscribers"

ASANA_WORKSHEET_NAME = "Asana_History"
# # If you have a page lookup tab, set it here
# PAGE_LOOKUP_WORKSHEET = "page_lookup"   # change this if your lookup tab has another name
# USE_PAGE_LOOKUP = False                 # change to True once your page lookup tab is ready

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

# =========================
# GOOGLE SHEETS LOAD
# =========================
def get_client():
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    return gspread.authorize(creds)

# @st.cache_data
# def load_sheet(sheet_url, worksheet_name):
#     client = get_client()
#     spreadsheet = client.open_by_url(sheet_url)
#     worksheet = spreadsheet.worksheet(worksheet_name)
#     data = worksheet.get_all_records()
#     df = pd.DataFrame(data)
    
#     return df

@st.cache_data
def load_sheet(sheet_url, worksheet_name):
    client = get_client()
    worksheet = client.open_by_url(sheet_url).worksheet(worksheet_name)

    all_values = worksheet.get_all_values()

    if not all_values:
        return pd.DataFrame()

    headers = all_values[0]
    rows = all_values[1:]

    print(f"Worksheet: {worksheet_name}")
    print("Header row raw:", headers)

    cleaned_headers = []
    seen = {}

    for i, h in enumerate(headers):
        h = str(h).strip()

        if h == "":
            h = f"Unnamed_{i+1}"

        if h in seen:
            seen[h] += 1
            h = f"{h}_{seen[h]}"
        else:
            seen[h] = 0

        cleaned_headers.append(h)

    max_len = len(cleaned_headers)
    normalized_rows = [row + [""] * (max_len - len(row)) for row in rows]

    df = pd.DataFrame(normalized_rows, columns=cleaned_headers)
    return df

# @st.cache_data
# def load_sheet_asana(sheet_url, worksheet_name):
#     client = get_client()
#     spreadsheet = client.open_by_url(sheet_url)
#     worksheet = spreadsheet.worksheet(worksheet_name)
#     data = worksheet.get_all_records()
#     df = pd.DataFrame(data)
#     headers = worksheet.row_values(1)
#     print("Headers:", headers)
#     return df
# =========================
# CLEANING
# =========================
def clean_asana_history(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.replace("", pd.NA)

    # -------------------------
    # Convert dates
    # -------------------------
    date_cols = [
        "created_at", "modified_at", "due_date",
        "completed_at", "last_modified_story_at", "extract_date"
    ]

    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # -------------------------
    # Clean text fields
    # -------------------------
    text_cols = [
        "Brand", "Assigned to Member", "status",
        "Task Relationship", "Task Category", "Task Type", "Project"
    ]

    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna("Unassigned").astype(str).str.strip()

    # -------------------------
    # Name Cleaning Logic
    # -------------------------
    def clean_name(name):
        if pd.isna(name):
            return "Unassigned"

        name = str(name).strip()
        
        # Special case
        if name.lower() == "a ranatunga":
            return "Anuki"

        # Normal case → take first word
        return name.split()[0]

    name_cols = ["last_modified_by", "Creator Member", "Assigned to Member"]

    for col in name_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_name)

    return df

CONTENT_WRITER_CATEGORIES = [
    "Caption Writing",
    "Content Writing Email/SMS",
    "Content Writing SM Artworks",
    "Content Writing – Other",
    "Article Writing",
]

DESIGNER_CATEGORIES = [
    "Artwork Edits",
    "Hoarding Design",
    "Leaflet Design",
    "Social Media Artwork Design",
    "Pull-Up Banner Design",
    "E-Banner Design",
    "Notebook Design",
    "Calendar Design",
    "E-Flyer Design",
    "Internal Artwork",
    "Logo Design",
    "Sign Board Design",
    "Brochure Design",
    "Paper Advertisement Design",
    "Template",
    "Merchandise Design",
    "Voucher/Print Design",
    "Reel Video",
    "Footage Video",
    "Animation Video",
    "TikTok Video",
    "Merchandise",
    "Image Resizing",
    "Approvals Design",
]

ANALYST_CATEGORIES = [
    "Dashboard Design",
    "Data Scraping",
    "Analyzing",
    "Bug Fixing",
    "Dummy Data Arrangement",
    "Data Collection",
    "Data Cleaning",
    "Coding",
    "Data Pipeline Development",
    "Approving",
    "Data Visualization",
    "Results & Evaluations",
    "Quarterly Reports",
]

ASSIGNEE_GROUP_MAP = {
    "Thisal": "Content Writer",
    "Anuki": "Designer",
    "Suhith": "Designer",
    "Abdullah": "Designer",
    "Sandunika": "Designer",
    "Udani": "Analyst",
    "Kiran": "Ops",
    "Shoaib": "Ops",
    "Maduka": "Ops",
    "Ruwangi": "Ops",
    "Ruchika": "Ops",
    "Atheeq": "Ops",
    "Nafhan": "Ops",
}

def render_asana_dashboard():
    col_title, col_logo = st.columns([6, 1])
    
    with col_title:
        st.title("Asana Workspace Dashboard")

    with col_logo:
        st.markdown(
            f"""
            <div style="
                display: flex;
                justify-content: center;
                align-items: center;
                margin-top: 10px;
            ">
                <div style="
                    width: 92px;
                    height: 92px;
                    border-radius: 50%;
                    border: 2px solid #FC5C38;
                    background-color: #081018;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    box-shadow: 0 0 10px rgba(24, 119, 242, 0.4);
                    overflow: hidden;
                ">
                    <img src="data:image/png;base64,{get_base64_image('Logos/Asana_LOGO.jpg')}"
                        style="
                            width: 78px;
                            height: 78px;
                            object-fit: contain;
                            border-radius: 50%;
                            background-color: white;
                            padding: 4px;
                        ">
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Load from separate Google Sheet
    df = load_sheet(ASANA_SHEET_URL, ASANA_WORKSHEET_NAME)
    df = clean_asana_history(df)
    
    latest_date = pd.to_datetime(df["extract_date"], errors="coerce").max()
    latest_date = latest_date.strftime("%b %d, %Y") if pd.notna(latest_date) else "N/A"

    st.markdown(
        f"""
        <div style="
            display:inline-block;
            padding:6px 16px;
            border-radius:20px;
            background:rgba(255, 140, 0, 0.15);
            color:#FC5C38;
            font-size:14px;
            font-weight:500;
            margin-top:-10px;
        ">
            📅 Task Performance & Productivity Overview &nbsp; · &nbsp;
            <b>{latest_date}</b>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")

    if df.empty:
        st.warning("No Asana data found.")
        return

    if "created_at" not in df.columns or df["created_at"].dropna().empty:
        st.error("created_at column is missing or empty in Asana data.")
        return

    # -------------------------
    # Filters
    # -------------------------
    st.sidebar.markdown("## Asana Filters")

    min_date = df["created_at"].dt.date.min()
    max_date = df["created_at"].dt.date.max()

    selected_date_range = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key="asana_date_range"
    )

    if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2:
        start_date, end_date = selected_date_range
    else:
        start_date, end_date = min_date, max_date

    brand_options = ["All"] + sorted(
        [x for x in df["Brand"].dropna().unique().tolist() if str(x).strip() != ""]
    )
    selected_brand = st.sidebar.selectbox("Brand", brand_options, key="asana_brand")

    assignee_options = ["All"] + sorted(
        [x for x in df["Assigned to Member"].dropna().unique().tolist() if str(x).strip() != ""]
    )
    selected_assignee = st.sidebar.selectbox("Assigned To", assignee_options, key="asana_assignee")

    creator_options = ["All"] + sorted(
        [x for x in df["Creator Member"].dropna().unique().tolist() if str(x).strip() != ""]
    )

    selected_creator = st.sidebar.selectbox(
        "Creator Member",
        creator_options,
        key="asana_creator"
    )
    # -------------------------
    # Apply filters
    # -------------------------
    filtered_df = df.copy()

    filtered_df = filtered_df[
        (filtered_df["created_at"].dt.date >= start_date) &
        (filtered_df["created_at"].dt.date <= end_date)
    ]

    if selected_brand != "All":
        filtered_df = filtered_df[filtered_df["Brand"] == selected_brand]

    if selected_assignee != "All":
        filtered_df = filtered_df[filtered_df["Assigned to Member"] == selected_assignee]

    if selected_creator != "All":
        filtered_df = filtered_df[
            filtered_df["Creator Member"] == selected_creator
        ]
    # -------------------------
    # KPIs
    # -------------------------
    total_tasks = len(filtered_df)

    completed_mask = filtered_df["status"].astype(str).str.strip().str.lower().isin([
        "completed",
        "completed on time",
        "complete"
    ])
    completed_df = filtered_df[completed_mask].copy()

    completion_rate = (len(completed_df) / total_tasks * 100) if total_tasks > 0 else 0

    completed_df["cycle_time_days"] = (
        completed_df["completed_at"] - completed_df["created_at"]
    ).dt.total_seconds() / 86400

    avg_cycle_time = completed_df["cycle_time_days"].dropna().mean()
    avg_cycle_time = 0 if pd.isna(avg_cycle_time) else avg_cycle_time

    # -------------------------
    # KPI Cards
    # -------------------------
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Tasks", f"{total_tasks}")
    c2.metric("Completion Rate %", f"{completion_rate:.2f}%")
    c3.metric("Avg Cycle Time Days", f"{avg_cycle_time:.2f}")

    st.divider()

    col1, col2 = st.columns(2)

    # -------- Chart 1: Status --------
    with col1:
        status_counts = (
            filtered_df["status"]
            .fillna("Unassigned")
            .astype(str)
            .str.strip()
            .value_counts()
            .reset_index()
        )
        status_counts.columns = ["Status", "Task Count"]

        fig1 = px.pie(
            status_counts,
            names="Status",
            values="Task Count",
            title="Task Distribution by Status"
        )

        fig1.update_traces(
            textinfo="percent+label",
            textposition="inside"
        )

        fig1.update_layout(
            showlegend=True,
            legend_title="Status",
            margin=dict(t=60, b=20, l=20, r=20),
            height=420
        )

        st.plotly_chart(fig1, use_container_width=True)

    # -------- Chart 2: Task Relationship --------
    with col2:
        task_rel_counts = (
            filtered_df["Task Relationship"]
            .fillna("Unassigned")
            .astype(str)
            .str.strip()
            .value_counts()
            .reset_index()
        )
        task_rel_counts.columns = ["Task Relationship", "Task Count"]

        fig2 = px.pie(
            task_rel_counts,
            names="Task Relationship",
            values="Task Count",
            title="Task Distribution by Task Relationship"
        )

        fig2.update_traces(
            textinfo="percent+label",
            textposition="inside"
        )

        fig2.update_layout(
            showlegend=True,
            legend_title="Task Relationship",
            margin=dict(t=60, b=20, l=20, r=20),
            height=420
        )

        st.plotly_chart(fig2, use_container_width=True)
    # -------------------------
    # Bar Charts Side by Side
    # -------------------------
    col3, col4 = st.columns(2)

    # -------- Chart 1: Tasks vs Brand --------
    with col3:
        brand_series = (
            filtered_df["Brand"]
            .fillna("Unassigned")
            .astype(str)
            .str.split(",")        # 🔥 split multiple brands
            .explode()             # 🔥 turn into rows
            .str.strip()           # clean spaces
        )

        brand_counts = (
            brand_series[brand_series != ""]
            .value_counts()
            .reset_index()
        )

        brand_counts.columns = ["Brand", "Task Count"]
        brand_counts = brand_counts.sort_values(by="Task Count", ascending=False)

        fig3 = px.bar(
            brand_counts,
            x="Brand",
            y="Task Count",
            title="Number of Tasks by Brand",
            text="Task Count"
        )

        fig3.update_layout(
            xaxis_title="Brand",
            yaxis_title="Number of Tasks",
            margin=dict(t=60, b=100, l=20, r=20),
            height=450,
            xaxis_tickangle=-30
        )

        st.plotly_chart(fig3, use_container_width=True)
    # -------- Chart 2: Tasks vs Task Category --------
    with col4:
        type_counts = (
            filtered_df["Task Type"]
            .fillna("Unassigned")
            .astype(str)
            .str.strip()
            .value_counts()
            .reset_index()
        )
        type_counts.columns = ["Task Type", "Task Count"]

        fig4 = px.bar(
            type_counts,
            x="Task Type",
            y="Task Count",
            title="Number of Tasks by Task Type",
            text="Task Count"
        )

        fig4.update_layout(
            xaxis_title="Task Type",
            yaxis_title="Number of Tasks",
            margin=dict(t=60, b=40, l=20, r=20),
            height=420
        )

        st.plotly_chart(fig4, use_container_width=True)

    # -------------------------
    # Task Category Bar Chart
    # -------------------------
    category_df = filtered_df.copy()

    category_df["Task Category Split"] = (
        category_df["Task Category"]
        .fillna("Unassigned")
        .astype(str)
        .str.split(",")
    )

    category_df = category_df.explode("Task Category Split")
    category_df["Task Category Split"] = category_df["Task Category Split"].str.strip()

    NON_OPS_CATEGORIES = set(
        CONTENT_WRITER_CATEGORIES +
        DESIGNER_CATEGORIES +
        ANALYST_CATEGORIES
    )

    if selected_assignee != "All":
        person_group = ASSIGNEE_GROUP_MAP.get(selected_assignee)

        if person_group == "Content Writer":
            category_df = category_df[
                category_df["Task Category Split"].isin(CONTENT_WRITER_CATEGORIES)
            ]

        elif person_group == "Designer":
            category_df = category_df[
                category_df["Task Category Split"].isin(DESIGNER_CATEGORIES)
            ]

        elif person_group == "Analyst":
            category_df = category_df[
                category_df["Task Category Split"].isin(ANALYST_CATEGORIES)
            ]

        elif person_group == "Ops":
            category_df = category_df[
                ~category_df["Task Category Split"].isin(NON_OPS_CATEGORIES)
            ]

    category_counts = (
        category_df["Task Category Split"]
        .dropna()
        .loc[lambda s: s != ""]
        .value_counts()
        .reset_index()
    )

    category_counts.columns = ["Task Category", "Task Count"]
    category_counts = category_counts.sort_values(by="Task Count", ascending=False)

    # Move "Unassigned" to the end
    if "Unassigned" in category_counts["Task Category"].values:
        unassigned_row = category_counts[category_counts["Task Category"] == "Unassigned"]
        category_counts = category_counts[category_counts["Task Category"] != "Unassigned"]
        category_counts = pd.concat([category_counts, unassigned_row], ignore_index=True)
    fig5 = px.bar(
        category_counts,
        x="Task Category",
        y="Task Count",
        title="Number of Tasks by Task Category",
        text="Task Count"
    )

    fig5.update_layout(
        xaxis_title="Task Category",
        yaxis_title="Number of Tasks",
        margin=dict(t=60, b=120, l=20, r=20),
        height=500,
        xaxis_tickangle=-35
    )

    st.plotly_chart(fig5, use_container_width=True)
    # # -------------------------
    # # Table
    # # -------------------------
    # preferred_cols = [
    #     "task_id", "task_name", "created_at", "modified_at", "due_date",
    #     "completed_at", "status", "last_modified_story_at", "last_modified_action",
    #     "last_modified_by", "subtask_count", "Creator Member", "Assigned to Member",
    #     "Task Relationship", "Task Category", "Task Type", "Project", "Brand",
    #     "extract_date", "unique_key"
    # ]

    # display_cols = [col for col in preferred_cols if col in filtered_df.columns]

    # if "created_at" in filtered_df.columns:
    #     filtered_df = filtered_df.sort_values(by="created_at", ascending=False)

    # st.dataframe(
    #     filtered_df[display_cols],
    #     use_container_width=True,
    #     hide_index=True
    # )

def clean_meta_ads_history(df: pd.DataFrame, page_lookup_df: pd.DataFrame = None) -> pd.DataFrame:
    df = df.copy()

    # replace empty strings
    df = df.replace("", pd.NA)

    # type conversions
    int_cols = [
        "actions_lead",
        "actions_post_engagement",
        "actor_id",
        "clicks",
        "impressions",
        "link_clicks",
        "reach",
        "unique_actions_link_click"
    ]

    float_cols = [
        "amount_spent",
        "cost_per_action_type_lead",
        "cpm",
        "ctr",
        "frequency",
        "outbound_clicks_ctr_outbound_click",
        "spend"
    ]

    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "ad_id" in df.columns:
        df["ad_id"] = df["ad_id"].astype(str)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce", format="%d/%m/%Y")

    if "extract_date" in df.columns:
        df["extract_date"] = pd.to_datetime(df["extract_date"], errors="coerce")

    # merge page lookup if available
    if page_lookup_df is not None and not page_lookup_df.empty:
        df["actor_id"] = df["actor_id"].astype(str).str.strip()
        page_lookup_df["Page ID"] = page_lookup_df["Page ID"].astype(str).str.strip()
        page_lookup_df["Page Name"] = page_lookup_df["Page Name"].astype(str).str.strip()
        
        # print("Page lookup columns:")
        # print(page_lookup_df.info())
        # print(page_lookup_df[["Page ID", "Page Name"]].head())
        
        df = df.merge(
            page_lookup_df[["Page ID", "Page Name"]],
            how="left",
            left_on="actor_id",
            right_on="Page ID"
        )
        # # debug
        # print("Merge check:")
        # print(df[["actor_id", "Page ID", "Page Name"]].drop_duplicates().head(20))

    # remove blank account rows
    if "account_name" in df.columns:
        df = df[df["account_name"].notna()]
        df = df[df["account_name"].astype(str).str.strip() != ""]

    # remove rows where both spend and impressions are zero
    if "spend" in df.columns and "impressions" in df.columns:
        df = df[~((df["spend"].fillna(0) == 0) & (df["impressions"].fillna(0) == 0))]

    # drop unwanted columns
    cols_to_drop = ["actor_id", "Page ID", "objective", "actions_post_engagement"]
    df = df.drop(columns=[c for c in cols_to_drop if c in df.columns], errors="ignore")

    # rename columns
    rename_map = {
        "Page Name": "Page_Name",
        "account_name": "Account_Name",
        "actions_lead": "Leads",
        "ad_id": "Ad_ID",
        "amount_spent": "Account_Spend",
        "campaign": "Campaign_Name",
        "campaign_objective": "Campaign_Objective",
        "clicks": "Clicks(all)",
        "cost_per_action_type_lead": "Cost_Per_Leads",
        "cpm": "CPM (cost per 1,000 impressions)",
        "ctr": "CTR (all)",
        "date": "Day",
        "frequency": "Frequency",
        "impressions": "Impressions",
        "link_clicks": "Link_clicks",
        "outbound_clicks_ctr_outbound_click": "Outbound_CTR_(click-through rate)",
        "platform_position": "Placement",
        "reach": "Reach",
        "spend": "Amount_Spent(USD)",
        "unique_actions_link_click": "Unique_link_clicks"
    }

    df = df.rename(columns=rename_map)

    # if no page lookup was used, create Page_Name from Account_Name so charts still work
    if "Page_Name" not in df.columns and "Account_Name" in df.columns:
        df["Page_Name"] = df["Account_Name"]

    # reorder
    final_column_order = [
        "Account_Name", "Leads", "Page_Name", "Ad_ID", "Account_Spend",
        "Campaign_Name", "Campaign_Objective", "Clicks(all)", "Cost_Per_Leads",
        "CPM (cost per 1,000 impressions)", "CTR (all)", "Day", "Frequency",
        "Impressions", "Link_clicks", "Outbound_CTR_(click-through rate)",
        "Placement", "Reach", "Amount_Spent(USD)", "Unique_link_clicks",
        "extract_date", "unique_key"
    ]

    existing_cols = [c for c in final_column_order if c in df.columns]
    df = df[existing_cols]

    return df

def clean_ga4_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.replace("", pd.NA)

    # standardize likely numeric columns
    numeric_cols = [
        "sessions",
        "active_users",
        "new_users",
        "average_session_duration",
        "average_interaction_time_per_session",
        "event_count",
        "screen_page_views",
        "engaged_sessions"
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # date parsing
    possible_date_cols = ["date", "day"]
    for col in possible_date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # account / brand cleanup
    if "account_name" in df.columns:
        df["account_name"] = df["account_name"].astype(str).str.strip()

    return df

def clean_mailerlite_campaigns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.replace("", pd.NA)

    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    if "extract_date" in df.columns:
        df["extract_date"] = pd.to_datetime(df["extract_date"], errors="coerce")
        
    if "finished_at" in df.columns:
        df["finished_at"] = pd.to_datetime(df["finished_at"], errors="coerce")
        df["finished_date"] = df["finished_at"].dt.date
        df["month"] = df["finished_at"].dt.strftime("%B")
        df["month_num"] = df["finished_at"].dt.month

    numeric_cols = [
        "sent",
        "deliveries_count",
        "unsubscribes_count",
        "hard_bounces_count",
        "soft_bounces_count",
        "opens_count",
        "clicks_count",
        "spam_count"
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    percent_cols = ["open_rate", "click_rate", "click_to_open_rate", "delivery_rate", "unsubscribe_rate"]

    for col in percent_cols:
        if col in df.columns:
            df[col] = parse_percent_series(df[col])

    if "from_name" in df.columns:
        df["from_name"] = df["from_name"].astype(str).str.strip()

    return df


def clean_mailerlite_subscribers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.replace("", pd.NA)

    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    if "extract_date" in df.columns:
        df["extract_date"] = pd.to_datetime(df["extract_date"], errors="coerce")

    if "from_name" in df.columns:
        df["from_name"] = df["from_name"].astype(str).str.strip()

    if "status" in df.columns:
        df["status"] = df["status"].astype(str).str.strip()

    return df

# =========================
# HELPERS
# =========================
def parse_percent_series(series):
    return (
        series.astype(str)
        .str.replace("%", "", regex=False)
        .str.strip()
        .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
        .pipe(pd.to_numeric, errors="coerce")
    )
import base64

def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

def format_duration(seconds):
    if pd.isna(seconds):
        return "0m 0s"

    seconds = int(round(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    return f"{minutes}m {secs}s"
def load_page_lookup():
    try:
        df = pd.read_csv("data/page_lookup.csv", sep=None, engine="python")
        df.columns = df.columns.str.strip()

        # df["Page ID"] = pd.to_numeric(df["Page ID"], errors="coerce").astype("Int64")
        # df["Page Name"] = df["Page Name"].astype(str).str.strip()

        df["Page ID"] = df["Page ID"].astype(str).str.strip()
        df["Page Name"] = df["Page Name"].astype(str).str.strip()

        return df

    except Exception as e:
        st.warning(f"Page lookup file error: {e}")
        return pd.DataFrame()

def safe_sum(series):
    return pd.to_numeric(series, errors="coerce").fillna(0).sum()

def safe_mean(series):
    s = pd.to_numeric(series, errors="coerce")
    s = s.dropna()
    return s.mean() if not s.empty else 0

def format_k(value, decimals=2):
    if value >= 1_000_000:
        return f"{value/1_000_000:.{decimals}f}M"
    if value >= 1_000:
        return f"{value/1_000:.{decimals}f}K"
    return f"{value:.{decimals}f}"

# =========================
# STREAMLIT APP
# =========================
def render_meta_ads_dashboard():
    col_title, col_logo = st.columns([6, 1])

    with col_title:
        st.title("Meta Ads Performance Dashboard")

    with col_logo:
        st.markdown(
            f"""
            <div style="
                display: flex;
                justify-content: center;
                align-items: center;
                margin-top: 10px;
            ">
                <div style="
                    width: 92px;
                    height: 92px;
                    border-radius: 50%;
                    border: 2px solid #1877F2;
                    background-color: #081018;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    box-shadow: 0 0 10px rgba(24, 119, 242, 0.4);
                    overflow: hidden;
                ">
                    <img src="data:image/png;base64,{get_base64_image('Logos/Meta_Logo.png')}"
                        style="
                            width: 78px;
                            height: 78px;
                            object-fit: contain;
                            border-radius: 50%;
                            background-color: white;
                            padding: 4px;
                        ">
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # load main data
    raw_df = load_sheet(SHEET_URL,META_WORKSHEET_NAME)

    # load page lookup optionally
    page_lookup_df = load_page_lookup()


    df = clean_meta_ads_history(raw_df, page_lookup_df)
    header_text = "Data unavailable"

    if "Day" in df.columns and "extract_date" in df.columns:

        max_data_date = pd.to_datetime(df["Day"], errors="coerce").max()
        max_extract_date = pd.to_datetime(df["extract_date"], errors="coerce").max()

        data_date_str = max_data_date.strftime("%b %d, %Y") if pd.notna(max_data_date) else "Unknown"
        refresh_str = max_extract_date.strftime("%b %d, %Y") if pd.notna(max_extract_date) else "Unknown"

        header_text = f"Data up to {data_date_str}  ·  Last refreshed {refresh_str}"
    st.markdown(
        f"""
        <div style="
            display:inline-block;
            padding:6px 16px;
            border-radius:20px;
            background:rgba(42, 164, 255, 0.15);
            color:#2aa4ff;
            font-size:14px;
            font-weight:500;
            margin-top:-10px;
        ">
            📅 Data up to <b>{data_date_str}</b> &nbsp; · &nbsp;
            🔄 Last refreshed <b>{refresh_str}</b>
        </div>
        """,
        unsafe_allow_html=True
    )
    # print(page_lookup_df.info())
    # print(df.info())

    if df.empty:
        st.error("No data available after cleaning.")
        st.stop()
    
    # =========================
    # FILTERS
    # =========================
    st.sidebar.header("Filters")

    if "Day" in df.columns:
        min_date = df["Day"].min()
        max_date = df["Day"].max()

        date_range = st.sidebar.date_input(
            "Date Range",
            value=(min_date.date(), max_date.date())
        )

        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
            df = df[(df["Day"] >= start_date) & (df["Day"] <= end_date)]

    page_options = ["All"]

    if "Page_Name" in df.columns:
        page_values = sorted(df["Page_Name"].dropna().astype(str).unique().tolist())
        page_options += page_values

    selected_page = st.sidebar.selectbox("Page Name", page_options)

    if selected_page != "All" and "Page_Name" in df.columns:
        df = df[df["Page_Name"] == selected_page]

    if df.empty:
        st.warning("No data after applying filters.")
        st.stop()
    st.markdown("---")
    # =========================
    # KPI CARDS
    # =========================
    total_spend = safe_sum(df["Amount_Spent(USD)"]) if "Amount_Spent(USD)" in df.columns else 0
    total_leads = safe_sum(df["Leads"]) if "Leads" in df.columns else 0
    total_impressions = safe_sum(df["Impressions"]) if "Impressions" in df.columns else 0
    avg_ctr = df["CTR (all)"].mean() * 100
    avg_cpm = safe_mean(df["CPM (cost per 1,000 impressions)"]) if "CPM (cost per 1,000 impressions)" in df.columns else 0
    avg_cpl = total_spend / total_leads if total_leads > 0 else 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    c1.metric("Total Spend", f"${format_k(total_spend)}")
    c2.metric("Total Leads", format_k(total_leads, 0))
    c3.metric("Total Impressions", format_k(total_impressions, 0))
    c4.metric("Average CTR", f"{avg_ctr:.2f}%")
    c5.metric("Average CPM", f"{avg_cpm:.2f}")
    c6.metric("Average CPL", f"{avg_cpl:.2f}")

    st.markdown("---")

    # =========================
    # CHARTS ROW 1
    # # =========================

    left_col, right_col = st.columns([1.1, 0.9])

    with left_col:
        st.subheader("Lead Volume by Placement")
        st.caption("Breakdown of total leads generated across ad placements")

        if "Placement" in df.columns and "Leads" in df.columns:
            placement_leads = (
                df.groupby("Placement", dropna=False)["Leads"]
                .sum()
                .reset_index()
            )

            placement_leads["Placement"] = placement_leads["Placement"].fillna("Unknown").astype(str).str.strip()
            placement_leads["Leads"] = pd.to_numeric(placement_leads["Leads"], errors="coerce").fillna(0)

            placement_leads = placement_leads[placement_leads["Leads"] > 0]
            placement_leads = placement_leads.sort_values("Leads", ascending=False).head(6)

            if not placement_leads.empty:
                fig = px.pie(
                    placement_leads,
                    values="Leads",
                    names="Placement",
                    hole=0.42
                )

                fig.update_traces(
                    textinfo="percent",
                    textfont_size=15,
                    hovertemplate="<b>%{label}</b><br>Leads: %{value}<br>%{percent}<extra></extra>"
                )

                fig.update_layout(
                    template="plotly_dark",
                    height=420,
                    width=520,
                    margin=dict(t=20, b=20, l=20, r=20),
                    font=dict(size=15),
                    legend=dict(
                        title="Placement",
                        font=dict(size=13),
                        title_font=dict(size=14),
                        x=1.02,
                        y=0.5
                    )
                )

                st.plotly_chart(fig, width="stretch")
            else:
                st.info("No placement data available.")


    with right_col:
        st.subheader("CPM, CTR by Placement")
        st.caption("Placement Performance Breakdown")

        required_cols = ["Placement", "CPM (cost per 1,000 impressions)", "CTR (all)", "Leads"]

        if all(col in df.columns for col in required_cols):
            placement_table = (
                df.groupby("Placement", dropna=False)
                .agg({
                    "CPM (cost per 1,000 impressions)": "mean",
                    "CTR (all)": "mean",
                    "Leads": "sum"
                })
                .reset_index()
                .rename(columns={
                    "CPM (cost per 1,000 impressions)": "Avg CPM",
                    "CTR (all)": "Avg CTR",
                    "Leads": "Total Leads"
                })
            )

            placement_table["Placement"] = placement_table["Placement"].fillna("Unknown").astype(str).str.strip()
            placement_table["Avg CPM"] = pd.to_numeric(placement_table["Avg CPM"], errors="coerce").round(2)
            placement_table["Avg CTR"] = (pd.to_numeric(placement_table["Avg CTR"], errors="coerce") * 100).round(2)
            placement_table["Total Leads"] = pd.to_numeric(placement_table["Total Leads"], errors="coerce").fillna(0).astype(int)

            placement_table = placement_table[placement_table["Total Leads"] > 0]
            placement_table = placement_table.sort_values("Total Leads", ascending=False).head(10)

            fig_table = go.Figure(
                data=[
                    go.Table(
                        header=dict(
                            values=["Placement", "Avg CPM", "Avg CTR", "Total Leads"],
                            fill_color="#1f1f1f",
                            align="left",
                            font=dict(color="white", size=14),
                            height=34
                        ),
                        cells=dict(
                            values=[
                                placement_table["Placement"],
                                placement_table["Avg CPM"],
                                placement_table["Avg CTR"].astype(str) + "%",
                                placement_table["Total Leads"]
                            ],
                            fill_color="#3a3a3a",
                            align="left",
                            font=dict(color="white", size=13),
                            height=30
                        )
                    )
                ]
            )

            fig_table.update_layout(
                template="plotly_dark",
                height=420,
                margin=dict(t=20, b=20, l=0, r=0)
            )

            st.plotly_chart(fig_table, width="stretch")
        else:
            st.info("Required columns missing for placement table.")

    left_col, right_col = st.columns([0.9, 1.1])

    with left_col:
        st.subheader("Budget Efficiency")
        st.caption("Impressions per $1 spent")

        if "Impressions" in df.columns and "Amount_Spent(USD)" in df.columns:
            total_impressions = pd.to_numeric(df["Impressions"], errors="coerce").fillna(0).sum()
            total_spend = pd.to_numeric(df["Amount_Spent(USD)"], errors="coerce").fillna(0).sum()

            impressions_per_dollar = total_impressions / total_spend if total_spend > 0 else 0

            gauge_fig = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=impressions_per_dollar,
                    number={"valueformat": ",.0f"},
                    title={"text": ""},
                    gauge={
                        "axis": {"range": [0, max(impressions_per_dollar * 1.3, 1000)]},
                        "bar": {"color": "#00b300", "thickness": 0.35},
                        "steps": [
                            {"range": [0, max(impressions_per_dollar * 0.4, 300)], "color": "#2a2a2a"},
                            {"range": [max(impressions_per_dollar * 0.4, 300), max(impressions_per_dollar * 0.8, 700)], "color": "#3a3a3a"},
                            {"range": [max(impressions_per_dollar * 0.8, 700), max(impressions_per_dollar * 1.3, 1000)], "color": "#4a4a4a"}
                        ]
                    }
                )
            )

            gauge_fig.update_layout(
                template="plotly_dark",
                height=320,
                margin=dict(t=50, b=20, l=20, r=20),
                font=dict(size=15)
            )

            st.plotly_chart(gauge_fig, width="stretch")
        else:
            st.info("Required columns missing for Budget Efficiency.")


    with right_col:
        st.subheader("Creative Fatigue")
        st.caption("CTR by Frequency Bucket")

        if "Frequency" in df.columns and "CTR (all)" in df.columns:
            fatigue_df = df.copy()

            fatigue_df["Frequency"] = pd.to_numeric(fatigue_df["Frequency"], errors="coerce")
            fatigue_df["CTR (all)"] = pd.to_numeric(fatigue_df["CTR (all)"], errors="coerce")

            fatigue_df["Frequency_Bucket"] = pd.cut(
                fatigue_df["Frequency"],
                bins=[0, 2, 3, 100],
                labels=["1-2x", "2-3x", "3x+"],
                include_lowest=True
            )

            fatigue_table = (
                fatigue_df.groupby("Frequency_Bucket", dropna=False)["CTR (all)"]
                .mean()
                .reset_index()
            )
            fatigue_table = fatigue_table[fatigue_table["Frequency_Bucket"].notna()]
            fatigue_table["CTR %"] = (fatigue_table["CTR (all)"] * 100).round(2)
            fatigue_table = fatigue_table[["Frequency_Bucket", "CTR %"]]

            # style matrix-like colors
            def color_ctr(val):
                if pd.isna(val):
                    return "background-color: #4a4a4a; color: white;"
                elif val >= 5:
                    return "background-color: #5b8f5b; color: white;"
                elif val >= 2:
                    return "background-color: #6f8f6f; color: white;"
                else:
                    return "background-color: #a85c5c; color: white;"

            styled_matrix = (
                fatigue_table.style
                .format({"CTR %": "{:.2f}%"})
                .map(color_ctr, subset=["CTR %"])
                .set_properties(**{
                    "background-color": "#3a3a3a",
                    "color": "white",
                    "border-color": "#5a5a5a",
                    "text-align": "center"
                })
                .set_table_styles([
                    {"selector": "th", "props": [("background-color", "#2f2f2f"), ("color", "white"), ("font-size", "14px")]},
                    {"selector": "td", "props": [("font-size", "14px"), ("padding", "8px")]},
                    {"selector": "table", "props": [("width", "100%"), ("border-collapse", "collapse")]}
                ])
            )

            st.dataframe(fatigue_table, width="stretch", hide_index=True)
        else:
            st.info("Required columns missing for Creative Fatigue.")
    
    st.markdown("---")

    st.subheader("Leads Over Time")
    st.caption("Daily lead trend over the selected period")

    required_cols = ["Day", "Leads"]

    if all(col in df.columns for col in required_cols):
        leads_df = df.copy()

        leads_df["Day"] = pd.to_datetime(leads_df["Day"], errors="coerce")
        leads_df["Leads"] = pd.to_numeric(leads_df["Leads"], errors="coerce").fillna(0)

        leads_df = leads_df[leads_df["Day"].notna()]

        leads_summary = (
            leads_df.groupby("Day", as_index=False)["Leads"]
            .sum()
            .sort_values("Day")
        )

        fig_leads = px.line(
            leads_summary,
            x="Day",
            y="Leads",
            markers=False
        )

        fig_leads.update_traces(
            line=dict(color="#2aa4ff", width=3)
        )

        fig_leads.update_layout(
            template="plotly_dark",
            height=450,
            margin=dict(t=20, b=20, l=20, r=20),
            xaxis_title="Date",
            yaxis_title="Total Leads",
            showlegend=False,
            font=dict(size=13)
        )

        fig_leads.update_xaxes(
            showgrid=True,
            gridcolor="rgba(255,255,255,0.2)",
            griddash="dot"
        )

        fig_leads.update_yaxes(
            showgrid=True,
            gridcolor="rgba(255,255,255,0.2)",
            griddash="dot"
        )

        st.plotly_chart(fig_leads, width="stretch")

    else:
        st.info("Required columns missing: Day, Leads")

def render_ga4_dashboard():
    col_title, col_logo = st.columns([6, 1])

    with col_title:
        st.title("GA4 Dashboard")
    with col_logo:
        st.markdown(
            f"""
            <div style="
                display: flex;
                justify-content: center;
                align-items: center;
                margin-top: 10px;
            ">
                <div style="
                    width: 92px;
                    height: 92px;
                    border-radius: 50%;
                    border: 2px solid #f9ab00;
                    background-color: #081018;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    box-shadow: 0 0 10px rgba(249, 171, 0, 0.4);
                    overflow: hidden;
                ">
                    <img src="data:image/png;base64,{get_base64_image('Logos/GA4.png')}"
                        style="
                            width: 78px;
                            height: 78px;
                            object-fit: contain;
                            border-radius: 50%;
                            background-color: white;
                            padding: 4px;
                        ">
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


    raw_df = load_sheet(SHEET_URL,GA4_WORKSHEET_NAME)
    df = clean_ga4_data(raw_df)
    data_date_str = "Unknown"
    refresh_str = "Unknown"

    if "date" in df.columns:
        max_data_date = pd.to_datetime(df["date"], errors="coerce").max()
        if pd.notna(max_data_date):
            data_date_str = max_data_date.strftime("%b %d, %Y")

    if "extract_date" in df.columns:
        max_extract_date = pd.to_datetime(df["extract_date"], errors="coerce").max()
        if pd.notna(max_extract_date):
            refresh_str = max_extract_date.strftime("%b %d, %Y")
            
    if df.empty:
        st.error("No GA4 data available after cleaning.")
        return
    st.markdown(
        f"""
        <div style="
            display:inline-block;
            padding:6px 16px;
            border-radius:20px;
            background:rgba(255, 140, 0, 0.15);
            color:#ff8c00;
            font-size:14px;
            font-weight:500;
            margin-top:-10px;
        ">
            📅 Data up to <b>{data_date_str}</b> &nbsp; · &nbsp;
            🔄 Last refreshed <b>{refresh_str}</b>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown("---")
    # -------------------------
    # Filters
    # -------------------------
    st.sidebar.header("Filters")

    if "date" in df.columns:
        min_date = df["date"].min()
        max_date = df["date"].max()

        if pd.notna(min_date) and pd.notna(max_date):
            date_range = st.sidebar.date_input(
                "GA4 Date Range",
                value=(min_date.date(), max_date.date()),
                key="ga4_date_range"
            )

            if isinstance(date_range, tuple) and len(date_range) == 2:
                start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
                df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]

    account_options = ["All"]
    if "account_name" in df.columns:
        account_values = sorted(df["account_name"].dropna().astype(str).unique().tolist())
        account_options += account_values

    selected_account = st.sidebar.selectbox("Account Name", account_options, key="ga4_account")

    if selected_account != "All" and "account_name" in df.columns:
        df = df[df["account_name"] == selected_account]

    if df.empty:
        st.warning("No GA4 data after applying filters.")
        return
    
    # -------------------------
    # KPI calculations (CORRECTED)
    # -------------------------

    # Total Sessions → event_name = session_start
    total_sessions = (
        df.loc[df["event_name"] == "session_start", "event_count"]
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
        .sum()
        if "event_name" in df.columns and "event_count" in df.columns
        else 0
    )

    # Total Active Users → event_name = session_start
    total_active_users = (
        df.loc[df["event_name"] == "session_start", "active_users"]
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
        .sum()
        if "event_name" in df.columns and "active_users" in df.columns
        else 0
    )

    # Total New Users → event_name = first_visit
    total_new_users = (
        df.loc[df["event_name"] == "first_visit", "newusers"]
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
        .sum()
        if "event_name" in df.columns and "newusers" in df.columns
        else 0
    )

    # -------------------------
    # Avg Session Duration (FIXED)
    # -------------------------

    avg_session_duration_seconds = 0

    if "event_name" in df.columns and "average_session_duration" in df.columns:
        duration_df = df[
            (df["event_name"] == "session_start") &
            (pd.to_numeric(df["average_session_duration"], errors="coerce") > 0)
        ].copy()

        duration_df["average_session_duration"] = pd.to_numeric(
            duration_df["average_session_duration"],
            errors="coerce"
        )

        avg_raw = duration_df["average_session_duration"].mean()

        if pd.notna(avg_raw):
            # 🔥 Smart detection (VERY IMPORTANT)
            # If values are tiny → they are fractions of a day → convert
            if avg_raw < 1:
                avg_session_duration_seconds = avg_raw * 86400
            else:
                avg_session_duration_seconds = avg_raw

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total Sessions", format_k(total_sessions))
    c2.metric("Total Active Users", format_k(total_active_users))
    c3.metric("Total New Users", format_k(total_new_users))
    c4.metric("Avg Session Duration", format_duration(avg_session_duration_seconds))

    st.markdown("---")

    left_col, right_col = st.columns([1.1, 0.9])

    # =========================
    # LEFT → BAR CHART (Events)
    # =========================
    with left_col:
        st.subheader("Event Count by Channel")
        st.caption("Total events broken down by acquisition channel")

        if "default_channel_group" in df.columns and "event_count" in df.columns:

            channel_df = df.copy()

            channel_df["default_channel_group"] = (
                channel_df["default_channel_group"]
                .fillna("Unassigned")
                .astype(str)
                .str.strip()
            )

            channel_df["event_count"] = pd.to_numeric(
                channel_df["event_count"], errors="coerce"
            ).fillna(0)

            channel_summary = (
                channel_df.groupby("default_channel_group")["event_count"]
                .sum()
                .reset_index()
                .sort_values("event_count", ascending=False)
            )

            # optional: top 8
            channel_summary = channel_summary.head(8)

            import plotly.express as px

            fig_bar = px.bar(
                channel_summary,
                x="event_count",
                y="default_channel_group",
                orientation="h",
                text="event_count"
            )

            fig_bar.update_traces(
                texttemplate="%{text:,.0f}",
                textposition="outside",
                marker_color="#ff8c00"
            )

            fig_bar.update_layout(
                template="plotly_dark",
                height=400,
                margin=dict(t=20, b=20, l=20, r=20),
                xaxis_title="Total Events",
                yaxis_title="",
                yaxis=dict(autorange="reversed"),
                font=dict(size=13)
            )

            st.plotly_chart(fig_bar, width="stretch")

        else:
            st.info("Required columns missing")


    # =========================
    # RIGHT → DONUT (Sessions)
    # =========================
    with right_col:
        st.subheader("Traffic by Channel")
        st.caption("Sessions breakdown by acquisition channel")

        if "default_channel_group" in df.columns and "event_count" in df.columns and "event_name" in df.columns:

            session_df = df[df["event_name"] == "session_start"].copy()

            session_df["default_channel_group"] = (
                session_df["default_channel_group"]
                .fillna("Unassigned")
                .astype(str)
                .str.strip()
            )

            session_df["event_count"] = pd.to_numeric(
                session_df["event_count"], errors="coerce"
            ).fillna(0)

            session_summary = (
                session_df.groupby("default_channel_group")["event_count"]
                .sum()
                .reset_index()
                .sort_values("event_count", ascending=False)
            )

            # optional: top 6
            session_summary = session_summary.head(6)

            import plotly.express as px

            fig_donut = px.pie(
                session_summary,
                values="event_count",
                names="default_channel_group",
                hole=0.5
            )

            fig_donut.update_traces(
                textinfo="percent",
                textfont_size=14,
                hovertemplate="<b>%{label}</b><br>Sessions: %{value:,}<br>%{percent}<extra></extra>"
            )

            fig_donut.update_layout(
                template="plotly_dark",
                height=400,
                margin=dict(t=20, b=20, l=20, r=20),
                legend=dict(title="Channel", font=dict(size=12))
            )

            st.plotly_chart(fig_donut, width="stretch")

        else:
            st.info("Required columns missing for donut")
    st.markdown("---")

    st.subheader("Session by Country")
    st.caption("Sessions and active users by country")

    if all(col in df.columns for col in ["country", "event_name", "event_count", "active_users"]):

        country_df = df[df["event_name"] == "session_start"].copy()

        country_df["country"] = (
            country_df["country"]
            .fillna("Unknown")
            .astype(str)
            .str.strip()
        )

        country_df["event_count"] = pd.to_numeric(country_df["event_count"], errors="coerce").fillna(0)
        country_df["active_users"] = pd.to_numeric(country_df["active_users"], errors="coerce").fillna(0)

        country_summary = (
            country_df.groupby("country", as_index=False)
            .agg({
                "event_count": "sum",
                "active_users": "sum"
            })
            .rename(columns={
                "event_count": "Total Sessions",
                "active_users": "Total Active Users"
            })
        )

        # remove blanks / unknowns if you don't want them on map
        country_summary = country_summary[
            country_summary["country"].notna() &
            (country_summary["country"].str.strip() != "") &
            (country_summary["country"].str.lower() != "unknown")
        ]

        if not country_summary.empty:
            fig_map = px.scatter_geo(
                country_summary,
                locations="country",
                locationmode="country names",
                size="Total Sessions",
                hover_name="country",
                hover_data={
                    "Total Sessions": ":,.0f",
                    "Total Active Users": ":,.0f"
                },
                projection="natural earth"
            )

            fig_map.update_traces(
                marker=dict(
                    color="#ff9900",
                    line=dict(width=0.8, color="#5a3a00"),
                    opacity=0.85
                )
            )

            fig_map.update_layout(
                template="plotly_dark",
                height=500,
                margin=dict(t=20, b=20, l=20, r=20),
                geo=dict(
                    showland=True,
                    landcolor="#d9d9d9",
                    showcountries=False,
                    showocean=True,
                    oceancolor="#bfbfbf",
                    showframe=False,
                    coastlinecolor="#bfbfbf",
                    bgcolor="rgba(0,0,0,0)"
                ),
                font=dict(size=13)
            )

            st.plotly_chart(fig_map, width="stretch")
        else:
            st.info("No country data available after filtering.")
    else:
        st.info("Required columns missing: country, event_name, event_count, active_users")
    
    st.markdown("---")

    left_col, right_col = st.columns(2)

    with left_col:
        st.subheader("Page Views Over Time by Channel")
        st.caption("Daily page views breakdown by acquisition channel")

        required_cols = ["date", "default_channel_group", "screen_page_views", "event_name"]

        if all(col in df.columns for col in required_cols):

            page_view_df = df[df["event_name"] == "page_view"].copy()

            page_view_df["date"] = pd.to_datetime(page_view_df["date"], errors="coerce")
            page_view_df["default_channel_group"] = (
                page_view_df["default_channel_group"]
                .fillna("Unassigned")
                .astype(str)
                .str.strip()
            )
            page_view_df["screen_page_views"] = pd.to_numeric(
                page_view_df["screen_page_views"], errors="coerce"
            ).fillna(0)

            page_view_df = page_view_df[page_view_df["date"].notna()]

            page_view_summary = (
                page_view_df.groupby(["date", "default_channel_group"], as_index=False)["screen_page_views"]
                .sum()
                .rename(columns={"screen_page_views": "Total Page Views"})
            )

            page_view_summary["default_channel_group"] = (
                page_view_summary["default_channel_group"]
                .str.replace("_", " ", regex=False)
                .str.title()
            )

            fig_line = px.line(
                page_view_summary,
                x="date",
                y="Total Page Views",
                color="default_channel_group",
                markers=False
            )

            fig_line.update_layout(
                template="plotly_dark",
                height=500,
                margin=dict(t=20, b=20, l=20, r=20),
                xaxis_title="Date",
                yaxis_title="Page Views",
                legend_title="default_channel_group",
                font=dict(size=13)
            )

            fig_line.update_xaxes(
                showgrid=True,
                gridcolor="rgba(255,255,255,0.2)",
                griddash="dot"
            )

            fig_line.update_yaxes(
                showgrid=True,
                gridcolor="rgba(255,255,255,0.2)",
                griddash="dot"
            )

            st.plotly_chart(fig_line, width="stretch")

        else:
            st.info("Required columns missing: date, default_channel_group, screen_page_views, event_name")


    with right_col:
        st.subheader("Total Sessions Over Time")
        st.caption("Daily sessions across all brands")

        required_cols = ["date", "event_name", "event_count"]

        if all(col in df.columns for col in required_cols):

            session_df = df[df["event_name"] == "session_start"].copy()

            session_df["date"] = pd.to_datetime(session_df["date"], errors="coerce")
            session_df["event_count"] = pd.to_numeric(
                session_df["event_count"], errors="coerce"
            ).fillna(0)

            session_df = session_df[session_df["date"].notna()]

            session_summary = (
                session_df.groupby("date", as_index=False)["event_count"]
                .sum()
                .rename(columns={"event_count": "Total Sessions"})
            )

            fig_sessions = px.line(
                session_summary,
                x="date",
                y="Total Sessions"
            )

            fig_sessions.update_traces(
                line=dict(color="#2aa4ff", width=3)
            )

            fig_sessions.update_layout(
                template="plotly_dark",
                height=500,
                margin=dict(t=20, b=20, l=20, r=20),
                xaxis_title="Date",
                yaxis_title="Total Sessions",
                showlegend=False,
                font=dict(size=13)
            )

            fig_sessions.update_xaxes(
                showgrid=True,
                gridcolor="rgba(255,255,255,0.2)",
                griddash="dot"
            )

            fig_sessions.update_yaxes(
                showgrid=True,
                gridcolor="rgba(255,255,255,0.2)",
                griddash="dot"
            )

            st.plotly_chart(fig_sessions, width="stretch")

        else:
            st.info("Required columns missing: date, event_name, event_count")

def prepare_mailerlite_monthly_trend(df: pd.DataFrame) -> pd.DataFrame:
    trend_df = df.copy()

    if "finished_at" not in trend_df.columns:
        return pd.DataFrame()

    trend_df = trend_df.dropna(subset=["finished_at"])

    monthly = (
        trend_df.groupby(["month_num", "month"], as_index=False)
        .agg({
            "open_rate": "mean",
            "click_rate": "mean"
        })
        .sort_values("month_num")
    )

    return monthly
import altair as alt
def plot_mailerlite_engagement_trend(monthly_df: pd.DataFrame):
    if monthly_df.empty:
        st.info("No campaign engagement trend data available.")
        return

    chart_data = monthly_df.melt(
        id_vars=["month_num", "month"],
        value_vars=["open_rate", "click_rate"],
        var_name="metric",
        value_name="rate"
    )

    chart_data["metric"] = chart_data["metric"].replace({
        "open_rate": "Avg Campaign Open Rate",
        "click_rate": "Avg Campaign Click Rate"
    })

    chart = (
        alt.Chart(chart_data)
        .mark_area(opacity=0.55)
        .encode(
            x=alt.X(
                "month:N",
                sort=monthly_df["month"].tolist(),
                title="Month"
            ),
            y=alt.Y(
                "rate:Q",
                title="Rate (%)"
            ),
            color=alt.Color(
                "metric:N",
                scale=alt.Scale(
                    domain=["Avg Campaign Open Rate", "Avg Campaign Click Rate"],
                    range=["#39d98a", "#0b5d3b"]
                ),
                legend=alt.Legend(title=None, orient="top")
            ),
            tooltip=[
                alt.Tooltip("month:N", title="Month"),
                alt.Tooltip("metric:N", title="Metric"),
                alt.Tooltip("rate:Q", title="Rate", format=".2f")
            ]
        )
        .properties(
            height=420,
            title="CAMPAIGN ENGAGEMENT TREND OVER TIME"
        )
    )

    st.altair_chart(chart, use_container_width=True)

def prepare_subscriber_status(df: pd.DataFrame):
    if "status" not in df.columns:
        return pd.DataFrame()

    status_df = (
        df.groupby("status")
        .size()
        .reset_index(name="count")
    )

    return status_df

def plot_subscriber_status(status_df: pd.DataFrame):
    if status_df.empty:
        st.info("No subscriber data available.")
        return

    color_map = {
        "active": "#238a4d",
        "unsubscribed": "#2ecc71",
        "bounced": "#e67e22",
        "junk": "#9b59b6"
    }

    chart = (
        alt.Chart(status_df)
        .mark_arc(innerRadius=0)  # full pie
        .encode(
            theta=alt.Theta(field="count", type="quantitative"),
            color=alt.Color(
                field="status",
                type="nominal",
                scale=alt.Scale(
                    domain=list(color_map.keys()),
                    range=list(color_map.values())
                ),
                legend=alt.Legend(title="Status", orient="top")
            ),
            tooltip=["status", "count"]
        )
        .properties(
            height=400,
            title="SUBSCRIBER STATUS BREAKDOWN"
        )
    )

    st.altair_chart(chart, use_container_width=True)

def prepare_campaign_list_health(df: pd.DataFrame) -> pd.DataFrame:
    required_cols = [
        "subject",
        "hard_bounces_count",
        "unsubscribes_count",
        "soft_bounces_count"
    ]

    if not all(col in df.columns for col in required_cols):
        return pd.DataFrame()

    health_df = (
        df.groupby("subject", as_index=False)
        .agg({
            "hard_bounces_count": "sum",
            "unsubscribes_count": "sum",
            "soft_bounces_count": "sum"
        })
    )

    health_df["total_issues"] = (
        health_df["hard_bounces_count"].fillna(0)
        + health_df["unsubscribes_count"].fillna(0)
        + health_df["soft_bounces_count"].fillna(0)
    )

    health_df = (
        health_df.sort_values("total_issues", ascending=False)
        .head(10)
        .sort_values("total_issues", ascending=True)
    )

    return health_df
import altair as alt

def plot_campaign_list_health(health_df: pd.DataFrame):
    if health_df.empty:
        st.info("No campaign list health data available.")
        return

    chart_data = health_df.melt(
        id_vars=["subject"],
        value_vars=["hard_bounces_count", "unsubscribes_count", "soft_bounces_count"],
        var_name="metric",
        value_name="count"
    )

    chart_data["metric"] = chart_data["metric"].replace({
        "hard_bounces_count": "Total Hard Bounces",
        "unsubscribes_count": "Total Unsubscribes",
        "soft_bounces_count": "Total Soft Bounces"
    })

    campaign_order = health_df["subject"].tolist()

    chart = (
        alt.Chart(chart_data)
        .mark_bar()
        .encode(
            y=alt.Y(
                "subject:N",
                sort=campaign_order,
                title="Campaign Name"
            ),
            x=alt.X(
                "count:Q",
                title="Count"
            ),
            color=alt.Color(
                "metric:N",
                scale=alt.Scale(
                    domain=[
                        "Total Hard Bounces",
                        "Total Unsubscribes",
                        "Total Soft Bounces"
                    ],
                    range=["#7bdcb5", "#0f5a38", "#e8743b"]
                ),
                legend=alt.Legend(title=None, orient="top")
            ),
            yOffset="metric:N",
            tooltip=[
                alt.Tooltip("subject:N", title="Campaign"),
                alt.Tooltip("metric:N", title="Metric"),
                alt.Tooltip("count:Q", title="Count")
            ]
        )
        .properties(
            height=500,
            title="CAMPAIGN LIST HEALTH"
        )
    )

    text = (
        alt.Chart(chart_data)
        .mark_text(
            align="left",
            baseline="middle",
            dx=5,
            fontSize=11,
            color="#666666"
        )
        .encode(
            y=alt.Y("subject:N", sort=campaign_order),
            x=alt.X("count:Q"),
            text=alt.Text("count:Q"),
            yOffset="metric:N"
        )
    )

    st.altair_chart(chart + text, use_container_width=True)

def prepare_top_open_rate_campaigns(df: pd.DataFrame) -> pd.DataFrame:
    required_cols = ["subject", "open_rate"]

    if not all(col in df.columns for col in required_cols):
        return pd.DataFrame()

    open_df = df.dropna(subset=["subject", "open_rate"]).copy()

    summary_df = (
        open_df.groupby("subject", as_index=False)
        .agg(avg_open_rate=("open_rate", "mean"))
    )

    summary_df = (
        summary_df.sort_values("avg_open_rate", ascending=False)
        .head(5)
    )

    summary_df["subject_short"] = summary_df["subject"].apply(
        lambda x: x if len(str(x)) <= 28 else str(x)[:28] + "..."
    )

    return summary_df

def plot_top_open_rate_campaigns_donut(open_rate_df: pd.DataFrame):
    if open_rate_df.empty:
        st.info("No campaign open rate data available.")
        return

    color_range = ["#0b4f2c", "#a8d5ba", "#238ae6", "#1f2ca3", "#e76f35"]

    base = alt.Chart(open_rate_df).encode(
        theta=alt.Theta("avg_open_rate:Q"),
        color=alt.Color(
            "subject_short:N",
            scale=alt.Scale(
                domain=open_rate_df["subject_short"].tolist(),
                range=color_range[:len(open_rate_df)]
            ),
            legend=alt.Legend(title="Campaign Name", orient="right")
        ),
        tooltip=[
            alt.Tooltip("subject:N", title="Campaign"),
            alt.Tooltip("avg_open_rate:Q", title="Avg Open Rate", format=".2f")
        ]
    )

    donut = base.mark_arc(innerRadius=95, outerRadius=175)

    st.altair_chart(
        donut.properties(
            height=420,
            title="AVG CAMPAIGN OPEN RATE BY CAMPAIGN NAME"
        ),
        use_container_width=True
    )

def render_mailerlite_dashboard():
    col_title, col_logo = st.columns([6, 1])

    with col_title:
        st.title("Email Campaign Analytics")

    with col_logo:
        st.markdown(
            f"""
            <div style="
                display: flex;
                justify-content: center;
                align-items: center;
                margin-top: 10px;
            ">
                <div style="
                    width: 92px;
                    height: 92px;
                    border-radius: 50%;
                    border: 2px solid #2ecc71;
                    background-color: #081018;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    box-shadow: 0 0 10px rgba(46, 204, 113, 0.35);
                    overflow: hidden;
                ">
                    <img src="data:image/png;base64,{get_base64_image('Logos/MailerLite_Logo.png')}"
                        style="
                            width: 78px;
                            height: 78px;
                            object-fit: contain;
                            border-radius: 50%;
                            background-color: white;
                            padding: 4px;
                        ">
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    campaigns_raw = load_sheet(SHEET_URL,MAILERLITE_CAMPAIGNS_WORKSHEET)
    subscribers_raw = load_sheet(SHEET_URL,MAILERLITE_SUBSCRIBERS_WORKSHEET)

    campaigns_df = clean_mailerlite_campaigns(campaigns_raw)
    subscribers_df = clean_mailerlite_subscribers(subscribers_raw)

    if campaigns_df.empty and subscribers_df.empty:
        st.error("No MailerLite data available.")
        return
    
    # -------------------------
    # Header freshness text
    # -------------------------
    subtitle_text = "MailerLite · All Campaigns · Unknown"

    if "last_updated" in campaigns_df.columns:
        latest_date = pd.to_datetime(campaigns_df["last_updated"], errors="coerce").max()

        if pd.notna(latest_date):
            formatted_date = latest_date.strftime("%d %b %Y")  # 16 Apr 2026 
            subtitle_text = f"MailerLite · All Campaigns · {formatted_date}"

    st.markdown(
        f"""
        <div style="
            display:inline-block;
            padding:6px 14px;
            border-radius:20px;
            background-color:rgba(0, 200, 83, 0.15);
            color:#00c853;
            font-size:14px;
            font-weight:500;
            margin-top:-10px;
        ">
            {subtitle_text}
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown("---")
    # -------------------------
    # Filters
    # -------------------------
    st.sidebar.header("Filters")

    if "finished_date" in campaigns_df.columns:
        min_date = campaigns_df["finished_date"].min()
        max_date = campaigns_df["finished_date"].max()

        if pd.notna(min_date) and pd.notna(max_date):
            date_range = st.sidebar.date_input(
                "Date Range",
                value=(min_date, max_date),
                key="mailerlite_date_range"
            )

            if isinstance(date_range, tuple) and len(date_range) == 2:
                start_date, end_date = date_range

                campaigns_df = campaigns_df[
                    (campaigns_df["finished_date"] >= start_date) &
                    (campaigns_df["finished_date"] <= end_date)
                ]

                if "finished_date" in subscribers_df.columns:
                    subscribers_df = subscribers_df[
                        (subscribers_df["finished_date"] >= start_date) &
                        (subscribers_df["finished_date"] <= end_date)
                    ]
    from_name_options = ["All"]
    if "from_name" in campaigns_df.columns:
        from_name_values = sorted(
            campaigns_df["from_name"].dropna().astype(str).str.strip().unique().tolist()
        )
        from_name_options += from_name_values

    selected_from_name = st.sidebar.selectbox(
        "From Name",
        from_name_options,
        key="mailerlite_from_name"
    )

    if selected_from_name != "All":
        if "from_name" in campaigns_df.columns:
            campaigns_df = campaigns_df[
                campaigns_df["from_name"].astype(str).str.strip() == selected_from_name
            ]

        if "from_name" in subscribers_df.columns:
            subscribers_df = subscribers_df[
                subscribers_df["from_name"].astype(str).str.strip() == selected_from_name
            ]

    if campaigns_df.empty and subscribers_df.empty:
        st.warning("No MailerLite data after applying filters.")
        return

    # -------------------------
    # KPI cards
    # -------------------------
    print(campaigns_df.info())
    print(campaigns_df[["open_rate", "click_rate"]].head(20))
    print(campaigns_df[["open_rate", "click_rate"]].dtypes)

    total_emails_sent = (
        pd.to_numeric(campaigns_df["sent"], errors="coerce").fillna(0).sum()
        if "sent" in campaigns_df.columns else 0
    )

    avg_campaign_open_rate = (
        parse_percent_series(campaigns_df["open_rate"]).mean()
        if "open_rate" in campaigns_df.columns else 0
    )

    avg_campaign_ctor = (
        parse_percent_series(campaigns_df["click_to_open_rate"]).mean()
        if "click_to_open_rate" in campaigns_df.columns else 0
    )

    avg_campaign_click_rate = (
        parse_percent_series(campaigns_df["click_rate"]).mean()
        if "click_rate" in campaigns_df.columns else 0
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total Emails Sent", format_k(total_emails_sent, 0))
    c2.metric("Avg Campaign Open Rate", f"{avg_campaign_open_rate:.1f}%")
    c3.metric("Avg Campaign CTOR", f"{avg_campaign_ctor:.2f}%")
    c4.metric("Avg Campaign Click Rate", f"{avg_campaign_click_rate:.2f}%")

    st.markdown("---")

    col1, col2 = st.columns([2, 1])  # 2:1 ratio (trend bigger, pie smaller)

    with col1:
        monthly_trend_df = prepare_mailerlite_monthly_trend(campaigns_df)
        st.markdown("### ")
        plot_mailerlite_engagement_trend(monthly_trend_df)
    with col2:
        status_df = prepare_subscriber_status(subscribers_df)
        st.markdown("### ")
        plot_subscriber_status(status_df)
    campaign_health_df = prepare_campaign_list_health(campaigns_df)
    plot_campaign_list_health(campaign_health_df)

    top_open_rate_df = prepare_top_open_rate_campaigns(campaigns_df)

    st.markdown(
        "<div style='text-align:center; font-style:italic; color:#666; margin-bottom:8px;'>Top 5 Campaigns</div>",
        unsafe_allow_html=True
    )

    plot_top_open_rate_campaigns_donut(top_open_rate_df)
    
# def main():
#     st.set_page_config(page_title="Marketing Dashboard", layout="wide")

#     meta_tab, ga4_tab, mailer_tab = st.tabs(
#         ["Meta Ads Dashboard", "GA4 Dashboard", "MailerLite Dashboard"]
#     )

#     with meta_tab:
#         render_meta_ads_dashboard()

#     with ga4_tab:
#         render_ga4_dashboard()

#     with mailer_tab:
#         render_mailerlite_dashboard()

def main():
    import streamlit as st

    st.set_page_config(page_title="Marketing Dashboard", layout="wide")
    
    selected_dashboard = st.segmented_control(
        "Performance Dashboard",
        [
            "Meta Ads Dashboard",
            "GA4 Dashboard",
            "MailerLite Dashboard",
            "Asana Dashboard"
        ],
        default="Meta Ads Dashboard"
    )

    if selected_dashboard == "Meta Ads Dashboard":
        render_meta_ads_dashboard()

    elif selected_dashboard == "GA4 Dashboard":
        render_ga4_dashboard()

    elif selected_dashboard == "MailerLite Dashboard":
        render_mailerlite_dashboard()

    elif selected_dashboard == "Asana Dashboard":
        render_asana_dashboard()
        
if __name__ == "__main__":
    main()
