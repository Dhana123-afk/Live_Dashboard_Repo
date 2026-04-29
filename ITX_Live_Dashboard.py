import gspread
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from google.oauth2.service_account import Credentials
import plotly.express as px
import plotly.graph_objects as go
import base64

# Configs
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NQSCTnd-YkdOGvWmdKj6tvwiezJUBe3lOG6WmqDL72U/edit?gid=501579247#gid=501579247"
ASANA_SHEET_URL = "https://docs.google.com/spreadsheets/d/19LEVmTAH2mv0NtIp89OdIZM9M1IRtKXFgb5UrJviZpo/edit?gid=87559203#gid=87559203"
GA4_SHEET_URL = "https://docs.google.com/spreadsheets/d/17y3D6JS8wx9FoLSqt_D5Oo0YxDf_9P6e5f4AMHsr5Rk/edit?gid=188778766#gid=188778766"
META_SHEET_URL = "https://docs.google.com/spreadsheets/d/1U3jMwHh-5_QvhHym_xnm5CtyMU3lodqa_rrpXGK3RN4/edit?gid=330376197#gid=330376197"

META_WORKSHEET_NAME = "Meta_Ads_History" #Meta warehouse tab
GA4_WORKSHEET_NAME = "GA4_History" #GA4 warehouse tab
MAILERLITE_CAMPAIGNS_WORKSHEET = "MailerLite_Campaigns" #Mailerlite tabs
MAILERLITE_SUBSCRIBERS_WORKSHEET = "MailerLite_Subscribers"
ASANA_WORKSHEET_NAME = "Asana_History" #Asana warehouse tab

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

#Load google services client 
def get_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    return gspread.authorize(creds)

# import json

# def get_client():
#     with open("credentials.json", "r") as f:
#         service_account_info = json.load(f)

#     creds = Credentials.from_service_account_info(
#         service_account_info,
#         scopes=SCOPES
#     )
#     return gspread.authorize(creds)

# Load the google sheet 
import time
import gspread

@st.cache_data(ttl=600)
def load_sheet(sheet_url, worksheet_name):
    client = get_client()

    for attempt in range(3):
        try:
            worksheet = client.open_by_url(sheet_url).worksheet(worksheet_name)
            all_values = worksheet.get_all_values()
            break
        except gspread.exceptions.APIError as e:
            if attempt == 2:
                st.error(f"Google Sheets is temporarily unavailable for {worksheet_name}. Please refresh in a minute.")
                return pd.DataFrame()
            time.sleep(3)
    else:
        return pd.DataFrame()

    if not all_values:
        return pd.DataFrame()

    headers = all_values[0]
    rows = all_values[1:]

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

    return pd.DataFrame(normalized_rows, columns=cleaned_headers)

#Data Cleaning 
#---Asana History
def clean_asana_history(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.replace("", pd.NA)

    #Convert the dates to date time format
    date_cols = [
        "created_at", "modified_at", "due_date",
        "completed_at", "last_modified_story_at", "extract_date"
    ]

    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Clean other fields
    text_cols = [
        "Brand", "Assigned to Member", "status",
        "Task Relationship", "Task Category", "Task Type", "Project"
    ]

    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna("Unassigned").astype(str).str.strip()

    #Function to clean the Name
    def clean_name(name):
        if pd.isna(name):
            return "Unassigned"

        name = str(name).strip()
        
        # Special case
        if name.lower() == "a ranatunga":
            return "Anuki"

        # Default case take the first name
        return name.split()[0]

    name_cols = ["last_modified_by", "Creator Member", "Assigned to Member"]

    for col in name_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_name)

    return df

#---Meta Ads History
def clean_meta_ads_history(df: pd.DataFrame, page_lookup_df: pd.DataFrame = None) -> pd.DataFrame:
    df = df.copy()
    df = df.replace("", pd.NA)

    int_cols = ["page_id", "clicks", "impressions"]
    float_cols = [
        "spend",
        "cost_per_lead",
        "cpm",
        "ctr",
        "frequency"
    ]

    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "ad_id" in df.columns:
        df["ad_id"] = df["ad_id"].astype(str).str.strip()

    if "page_id" in df.columns:
        df["page_id"] = df["page_id"].astype(str).str.strip()

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)

    if "extract_date" in df.columns:
        df["extract_date"] = pd.to_datetime(df["extract_date"], errors="coerce")

    text_cols = [
        "account_name", "campaign", "objective",
        "object_type", "publisher_platform", "platform_position", "unique_key"
    ]

    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Page lookup using page_id
    if page_lookup_df is not None and not page_lookup_df.empty and "page_id" in df.columns:
        page_lookup_df = page_lookup_df.copy()
        page_lookup_df["Page ID"] = page_lookup_df["Page ID"].astype(str).str.strip()
        page_lookup_df["Page Name"] = page_lookup_df["Page Name"].astype(str).str.strip()

        df = df.merge(
            page_lookup_df[["Page ID", "Page Name"]],
            how="left",
            left_on="page_id",
            right_on="Page ID"
        )

    if "account_name" in df.columns:
        df = df[df["account_name"].notna()]
        df = df[df["account_name"].astype(str).str.strip() != ""]

    rename_map = {
        "Page Name": "Page_Name"
    }

    df = df.rename(columns=rename_map)

    final_columns = [
        "account_name",
        "Page_Name",
        "ad_id",
        "campaign",
        "objective",
        "page_id",
        "object_type",
        "publisher_platform",
        "platform_position",
        "date",
        "clicks",
        "spend",
        "leads",
        "cost_per_lead",
        "frequency",
        "cpm",
        "ctr",
        "impressions",
        "extract_date",
        "unique_key"
    ]

    existing_cols = [c for c in final_columns if c in df.columns]
    df = df[existing_cols]

    return df

#Roles to People maping
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

#----GA4 History
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

#---MailerLite Campaigns
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

#----Mailerlite Subscribers
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


# Helper Functions
def parse_percent_series(series):
    return (
        series.astype(str)
        .str.replace("%", "", regex=False)
        .str.strip()
        .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
        .pipe(pd.to_numeric, errors="coerce")
    )

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

    brand_series = (
        df["Brand"]
        .dropna()
        .astype(str)
        .str.split(",")   # split
        .explode()        # separate rows
        .str.strip()      # clean spaces
    )

    brand_options = ["All"] + sorted(
        [b for b in brand_series.dropna().unique().tolist() if str(b).strip() != ""]
    )
    selected_brand = st.sidebar.selectbox("Brand", brand_options, key="asana_brand")

    assignee_options = ["All"] + sorted(
        [x for x in df["Assigned to Member"].dropna().unique().tolist() if str(x).strip() != ""]
    )
    selected_assignee = st.sidebar.selectbox("Assigned To", assignee_options, key="asana_assignee")

    # -------------------------
    # Apply filters
    # -------------------------
    filtered_df = df.copy()

    filtered_df = filtered_df[
        (filtered_df["created_at"].dt.date >= start_date) &
        (filtered_df["created_at"].dt.date <= end_date)
    ]

    if selected_brand != "All":
        filtered_df = filtered_df[
            filtered_df["Brand"].str.contains(selected_brand, na=False)
        ]

    if selected_assignee != "All":
        filtered_df = filtered_df[filtered_df["Assigned to Member"] == selected_assignee]

    st.sidebar.divider()

    if st.sidebar.button("Download Dashboard View"):
        st.sidebar.info("Press Ctrl + P, then choose 'Save as PDF'.")
    # KPIs
    total_tasks = len(filtered_df)

    today = pd.Timestamp.today().normalize()

    completed_mask = filtered_df["status"].astype(str).str.strip().str.lower().isin([
        "completed",
        "completed on time",
        "complete"
    ])

    overdue_mask = (
        filtered_df["due_date"].notna() &
        (filtered_df["due_date"] < today) &
        (~completed_mask)
    )

    overdue_tasks = overdue_mask.sum()
    overdue_percentage = (overdue_tasks / total_tasks * 100) if total_tasks > 0 else 0

    completed_df = filtered_df[completed_mask].copy()

    completed_df["cycle_time_days"] = (
        completed_df["completed_at"] - completed_df["created_at"]
    ).dt.total_seconds() / 86400

    avg_cycle_time = completed_df["cycle_time_days"].dropna().mean()
    avg_cycle_time = 0 if pd.isna(avg_cycle_time) else avg_cycle_time

    # KPI cards
    # -------------------------
    c1, c2, c3 = st.columns(3)

    c1.metric("Total Tasks", f"{total_tasks}")
    c2.metric("% Overdue Tasks", f"{overdue_percentage:.2f}%")
    c3.metric("Avg Cycle Time Days", f"{avg_cycle_time:.2f}")
    st.divider()

    #col1, col2 = st.columns(2)

    # Stacked Bar: Task Status by Assignee
    # -------------------------
    task_status_df = filtered_df.copy()

    today = pd.Timestamp.today().normalize()

    completed_mask = task_status_df["status"].astype(str).str.strip().str.lower().isin([
        "completed",
        "completed on time",
        "complete"
    ])

    overdue_mask = (
        task_status_df["due_date"].notna() &
        (task_status_df["due_date"] < today) &
        (~completed_mask)
    )

    task_status_df["Task Status Group"] = "Not Completed"
    task_status_df.loc[completed_mask, "Task Status Group"] = "Completed"
    task_status_df.loc[overdue_mask, "Task Status Group"] = "Overdue"

    status_by_assignee = (
        task_status_df
        .groupby(["Assigned to Member", "Task Status Group"])
        .size()
        .reset_index(name="Task Count")
    )

    fig_status_assignee = px.bar(
        status_by_assignee,
        x="Assigned to Member",
        y="Task Count",
        color="Task Status Group",
        title="Task Count by Assigned Member and Status",
        text="Task Count",
        barmode="stack",
        category_orders={
            "Task Status Group": ["Overdue", "Not Completed", "Completed"]
        }
    )

    fig_status_assignee.update_layout(
        xaxis_title="Assigned to Member",
        yaxis_title="Task Count",
        height=520,
        margin=dict(t=60, b=120, l=20, r=20),
        xaxis_tickangle=-30,
        legend_title="Task Status"
    )

    st.plotly_chart(fig_status_assignee, use_container_width=True)

    # -------------------------
    # Stacked Bar: Task Status by Task Category
    # -------------------------
    st.subheader("Task Status by Task Category")
    st.caption("Breakdown of completed, not completed, and overdue tasks by category")

    task_cat_df = filtered_df.copy()

    today = pd.Timestamp.today().normalize()

    # Define masks
    completed_mask = task_cat_df["status"].astype(str).str.strip().str.lower().isin([
        "completed",
        "completed on time",
        "complete"
    ])

    overdue_mask = (
        task_cat_df["due_date"].notna() &
        (task_cat_df["due_date"] < today) &
        (~completed_mask)
    )

    # Assign status groups
    task_cat_df["Task Status Group"] = "Not Completed"
    task_cat_df.loc[completed_mask, "Task Status Group"] = "Completed"
    task_cat_df.loc[overdue_mask, "Task Status Group"] = "Overdue"

    # Split Task Category (important because yours has multiple values)
    task_cat_df["Task Category Split"] = (
        task_cat_df["Task Category"]
        .fillna("Unassigned")
        .astype(str)
        .str.split(",")
    )

    task_cat_df = task_cat_df.explode("Task Category Split")
    task_cat_df["Task Category Split"] = task_cat_df["Task Category Split"].str.strip()

    # Aggregate
    status_by_category = (
        task_cat_df
        .groupby(["Task Category Split", "Task Status Group"])
        .size()
        .reset_index(name="Task Count")
    )

    # Plot
    fig_status_category = px.bar(
        status_by_category,
        x="Task Category Split",
        y="Task Count",
        color="Task Status Group",
        title="Task Count by Category and Status",
        text="Task Count",
        barmode="stack",
        category_orders={
            "Task Status Group": ["Overdue", "Not Completed", "Completed"]
        }
    )

    fig_status_category.update_layout(
        xaxis_title="Task Category",
        yaxis_title="Task Count",
        height=520,
        margin=dict(t=60, b=120, l=20, r=20),
        xaxis_tickangle=-35,
        legend_title="Task Status"
    )

    st.plotly_chart(fig_status_category, use_container_width=True)

    # -------------------------
    # Line Chart: Tasks Created vs Completed Over Time
    # -------------------------
    st.subheader("Tasks Created vs Completed Over Time")
    st.caption("Daily trend of new tasks created compared with completed tasks")

    trend_df = filtered_df.copy()

    # Created tasks by date
    created_trend = (
        trend_df.dropna(subset=["created_at"])
        .assign(Date=trend_df["created_at"].dt.date)
        .groupby("Date")
        .size()
        .reset_index(name="Task Count")
    )

    created_trend["Metric"] = "Tasks Created"

    # Completed tasks by date
    completed_trend = (
        trend_df.dropna(subset=["completed_at"])
        .assign(Date=trend_df["completed_at"].dt.date)
        .groupby("Date")
        .size()
        .reset_index(name="Task Count")
    )

    completed_trend["Metric"] = "Tasks Completed"

    # Combine
    trend_summary = pd.concat(
        [created_trend, completed_trend],
        ignore_index=True
    )

    if not trend_summary.empty:
        fig_trend = px.line(
            trend_summary,
            x="Date",
            y="Task Count",
            color="Metric",
            markers=True,
            title="Tasks Created vs Completed Trend"
        )

        fig_trend.update_layout(
            xaxis_title="Date",
            yaxis_title="Task Count",
            height=500,
            margin=dict(t=60, b=80, l=20, r=20),
            legend_title=""
        )

        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("No created or completed task dates available.")
    
   

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
    raw_df = load_sheet(META_SHEET_URL,META_WORKSHEET_NAME)

    # load page lookup optionally
    page_lookup_df = load_page_lookup()


    df = clean_meta_ads_history(raw_df, page_lookup_df)
    header_text = "Data unavailable"

    data_date_str = "Unknown"
    refresh_str = "Unknown"

    if "date" in df.columns and "extract_date" in df.columns:

        max_data_date = pd.to_datetime(df["date"], errors="coerce").max()
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
    print(df.info())

    if df.empty:
        st.error("No data available after cleaning.")
        st.stop()
    
    # =========================
    # FILTERS
    # =========================
    st.sidebar.header("Filters")

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        min_date = df["date"].min()
        max_date = df["date"].max()

        if pd.notna(min_date) and pd.notna(max_date):
            date_range = st.sidebar.date_input(
                "Date Range",
                value=(min_date.date(), max_date.date()),
                key="meta_date_range"
            )

            if isinstance(date_range, tuple) and len(date_range) == 2:
                start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
                df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]

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

    st.sidebar.divider()

    if st.sidebar.button("Download Dashboard View"):
        st.sidebar.info("Press Ctrl + P, then choose 'Save as PDF' to download this dashboard view.")
    st.markdown("---")
    # =========================
    # KPI CARDS
    # =========================
    total_spend = safe_sum(df["spend"]) if "spend" in df.columns else 0
    total_clicks = safe_sum(df["clicks"]) if "clicks" in df.columns else 0
    total_impressions = safe_sum(df["impressions"]) if "impressions" in df.columns else 0
    avg_ctr = safe_mean(df["ctr"]) if "ctr" in df.columns else 0
    avg_cpm = safe_mean(df["cpm"]) if "cpm" in df.columns else 0
    

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Total Spend", f"${format_k(total_spend)}")
    c2.metric("Total Clicks", format_k(total_clicks, 0))
    c3.metric("Total Impressions", format_k(total_impressions, 0))
    c4.metric("Average CTR", f"{avg_ctr:.2f}%")
    c5.metric("Average CPM", f"${avg_cpm:.2f}")
    st.markdown("---")

    # =========================
    # CHARTS ROW 1
    # # =========================

    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.subheader("Clicks by Publisher Platform")
        st.caption("Breakdown of total clicks across Meta platforms")

        platform_map = {
            "facebook": "Facebook",
            "instagram": "Instagram",
            "messenger": "Messenger",
            "audience_network": "Audience Network",
            "whatsapp": "WhatsApp",
            "unknown": "Unknown"
        }

        if "publisher_platform" in df.columns and "clicks" in df.columns:
            platform_df = df.copy()

            platform_df["publisher_platform_clean"] = (
                platform_df["publisher_platform"]
                .fillna("unknown")
                .astype(str)
                .str.strip()
                .str.lower()
                .map(platform_map)
                .fillna("Other")
            )

            platform_df["clicks"] = pd.to_numeric(
                platform_df["clicks"],
                errors="coerce"
            ).fillna(0)

            platform_clicks = (
                platform_df.groupby("publisher_platform_clean", dropna=False)["clicks"]
                .sum()
                .reset_index()
                .rename(columns={
                    "publisher_platform_clean": "Publisher Platform",
                    "clicks": "Clicks"
                })
            )

            platform_clicks = platform_clicks[platform_clicks["Clicks"] > 0]
            platform_clicks = platform_clicks.sort_values("Clicks", ascending=False)

            if not platform_clicks.empty:
                fig = px.pie(
                    platform_clicks,
                    values="Clicks",
                    names="Publisher Platform",
                    hole=0.42
                )

                fig.update_traces(
                    textinfo="percent",
                    textfont_size=15,
                    hovertemplate="<b>%{label}</b><br>Clicks: %{value}<br>%{percent}<extra></extra>"
                )

                fig.update_layout(
                    template="plotly_dark",
                    height=420,
                    margin=dict(t=20, b=20, l=20, r=20),
                    font=dict(size=15),
                    legend=dict(
                        title="Publisher Platform",
                        font=dict(size=13),
                        title_font=dict(size=14),
                        x=1.02,
                        y=0.5
                    )
                )

                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No click data available by publisher platform.")
        else:
            st.info("Required columns missing: publisher_platform, clicks")
        
    with right_col:
        st.subheader("Clicks by Content Type")
        st.caption("Breakdown of clicks by ad creative format")

        if "object_type" in df.columns and "clicks" in df.columns:
            object_df = df.copy()

            object_map = {
                "SHARE": "Boosted Posts",
                "PHOTO": "Image Ads",
                "STATUS": "Text Posts",
                "VIDEO": "Video Ads"
            }

            object_df["object_type_clean"] = (
                object_df["object_type"]
                .fillna("Unknown")
                .astype(str)
                .str.strip()
                .str.upper()
                .map(object_map)
                .fillna("Other")
            )

            object_df["clicks"] = pd.to_numeric(
                object_df["clicks"],
                errors="coerce"
            ).fillna(0)

            object_clicks = (
                object_df.groupby("object_type_clean")["clicks"]
                .sum()
                .reset_index()
                .rename(columns={
                    "object_type_clean": "Content Type",
                    "clicks": "Clicks"
                })
            )

            object_clicks = object_clicks[object_clicks["Clicks"] > 0]
            object_clicks = object_clicks.sort_values("Clicks", ascending=False)

            if not object_clicks.empty:
                fig = px.pie(
                    object_clicks,
                    values="Clicks",
                    names="Content Type",
                    hole=0.42
                )

                fig.update_traces(
                    textinfo="percent",
                    textfont_size=15,
                    hovertemplate="<b>%{label}</b><br>Clicks: %{value}<br>%{percent}<extra></extra>"
                )

                fig.update_layout(
                    template="plotly_dark",
                    height=420,
                    margin=dict(t=20, b=20, l=20, r=20),
                    font=dict(size=15),
                    legend=dict(
                        title="Content Type",
                        font=dict(size=13),
                        title_font=dict(size=14),
                        x=1.02,
                        y=0.5
                    )
                )

                st.plotly_chart(fig, use_container_width=True)

            else:
                st.info("No data available for object types.")
        else:
            st.info("Required columns missing: object_type, clicks")
    

    left_col, right_col = st.columns([0.7, 1.1])

    with left_col:
        st.subheader("Budget Efficiency")
        st.caption("Impressions per $1 spent")

        if "impressions" in df.columns and "spend" in df.columns:
            total_impressions = pd.to_numeric(df["impressions"], errors="coerce").fillna(0).sum()
            total_spend = pd.to_numeric(df["spend"], errors="coerce").fillna(0).sum()

            impressions_per_dollar = total_impressions / total_spend if total_spend > 0 else 0

            gauge_fig = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=impressions_per_dollar,
                    number={"valueformat": ",.0f"},
                    gauge={
                        "axis": {"range": [0, max(impressions_per_dollar * 1.3, 1000)]},
                        "bar": {"color": "#00b300", "thickness": 0.35},
                    }
                )
            )

            gauge_fig.update_layout(
                template="plotly_dark",
                height=320,
                margin=dict(t=50, b=20, l=20, r=20),
                font=dict(size=15)
            )

            st.plotly_chart(gauge_fig, use_container_width=True)
        else:
            st.info("Required columns missing: impressions, spend")

    with right_col:
        st.subheader("Creative Fatigue")
        st.caption("CTR by Frequency Bucket")

        if "frequency" in df.columns and "ctr" in df.columns:
            fatigue_df = df.copy()

            fatigue_df["frequency"] = pd.to_numeric(fatigue_df["frequency"], errors="coerce")
            fatigue_df["ctr"] = pd.to_numeric(fatigue_df["ctr"], errors="coerce")

            fatigue_df["Frequency Bucket"] = pd.cut(
                fatigue_df["frequency"],
                bins=[0, 2, 3, 100],
                labels=["1-2x", "2-3x", "3x+"],
                include_lowest=True
            )

            fatigue_table = (
                fatigue_df.groupby("Frequency Bucket", dropna=False)["ctr"]
                .mean()
                .reset_index()
            )

            fatigue_table = fatigue_table[fatigue_table["Frequency Bucket"].notna()]
            fatigue_table["CTR %"] = fatigue_table["ctr"].round(2)
            fatigue_table = fatigue_table[["Frequency Bucket", "CTR %"]]

            st.dataframe(fatigue_table, use_container_width=True, hide_index=True)
        else:
            st.info("Required columns missing: frequency, ctr")
    # -------------------------
    # Leads Over Time
    # -------------------------
    st.subheader("Leads Over Time")
    st.caption("Daily lead trend over the selected period")

    if "date" in df.columns and "leads" in df.columns:
        leads_df = df.copy()

        leads_df["date"] = pd.to_datetime(leads_df["date"], errors="coerce")
        leads_df["leads"] = pd.to_numeric(leads_df["leads"], errors="coerce").fillna(0)

        leads_df = leads_df[leads_df["date"].notna()]

        leads_summary = (
            leads_df.groupby("date", as_index=False)["leads"]
            .sum()
            .sort_values("date")
            .rename(columns={"date": "Date", "leads": "Total Leads"})
        )

        if not leads_summary.empty:
            fig_leads = px.line(
                leads_summary,
                x="Date",
                y="Total Leads",
                markers=False
            )

            fig_leads.update_traces(
                line=dict(color="#2aa4ff", width=3)
            )

            fig_leads.update_layout(
                height=520,
                margin=dict(t=40, b=40, l=20, r=20),
                xaxis_title="Date",
                yaxis_title="Total Leads",
                showlegend=False,
                font=dict(size=13)
            )

            fig_leads.update_xaxes(
                showgrid=True,
                gridcolor="rgba(120,120,120,0.25)",
                griddash="dot"
            )

            fig_leads.update_yaxes(
                showgrid=True,
                gridcolor="rgba(120,120,120,0.25)",
                griddash="dot"
            )

            st.plotly_chart(fig_leads, use_container_width=True)
        else:
            st.info("No lead data available for the selected period.")
    else:
        st.info("Required columns missing: date, leads")
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


    raw_df = load_sheet(GA4_SHEET_URL,GA4_WORKSHEET_NAME)
    df = clean_ga4_data(raw_df)
    data_date_str = "Unknown"
    refresh_str = "Unknown"

    data_date_str = "Unknown"
    refresh_str = "Unknown"

    if "date" in df.columns:
        max_data_date = pd.to_datetime(df["date"], errors="coerce").max()
        data_date_str = max_data_date.strftime("%b %d, %Y") if pd.notna(max_data_date) else "Unknown"

    if "extract_date" in df.columns:
        max_extract_date = pd.to_datetime(df["extract_date"], errors="coerce").max()
        refresh_str = max_extract_date.strftime("%b %d, %Y") if pd.notna(max_extract_date) else "Unknown"
            
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
    st.sidebar.divider()
    if st.sidebar.button("Download Dashboard View"):
        st.sidebar.info("Press Ctrl + P, then choose 'Save as PDF' to download this dashboard view.")
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
    st.sidebar.divider()
    
    if st.sidebar.button("Download Dashboard View"):
        st.sidebar.info("Press Ctrl + P, then choose 'Save as PDF' to download this dashboard view.")
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
