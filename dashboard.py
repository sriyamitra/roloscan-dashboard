"""
RoloScan Dashboard
Run with:  streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RoloScan Dashboard",
    page_icon="📊",
    layout="wide",
)

OUTPUT_DIR = "output"

# ── Load data ──────────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    daily    = pd.read_csv(f"{OUTPUT_DIR}/daily_analytics_enriched.csv", parse_dates=["scan_date"])
    activity = pd.read_csv(f"{OUTPUT_DIR}/user_activity_enriched.csv",   parse_dates=["summary_date"])
    access   = pd.read_csv(f"{OUTPUT_DIR}/access_enriched.csv",          parse_dates=["signup_date"])
    org      = pd.read_csv(f"{OUTPUT_DIR}/org_summary.csv")
    return daily, activity, access, org

daily, activity, access, org = load_data()

all_orgs   = sorted(daily["org_name"].unique())
all_months = sorted(daily["year_month"].unique())

# ── Sidebar — global filters ───────────────────────────────────────────────────
st.sidebar.title("Filters")

selected_orgs = st.sidebar.multiselect(
    "Organisations",
    options=all_orgs,
    default=all_orgs,
    help="Select one or more organisations to filter all tabs",
)

selected_months = st.sidebar.multiselect(
    "Month",
    options=all_months,
    default=all_months,
)

if not selected_orgs:
    selected_orgs = all_orgs
if not selected_months:
    selected_months = all_months

daily_f    = daily[daily["org_name"].isin(selected_orgs) & daily["year_month"].isin(selected_months)]
activity_f = activity[activity["org_name"].isin(selected_orgs) & activity["year_month"].isin(selected_months)]
org_f      = org[org["org_name"].isin(selected_orgs)]

# ── Title ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; }
    [data-testid="stSidebar"] { background-color: #F0F2F6; }
    body, .stMarkdown, p, h1, h2, h3 { color: #1A1A1A; }
</style>
""", unsafe_allow_html=True)

st.title("RoloScan Dashboard")
st.caption("Use the sidebar to filter by organisation or month across all tabs.")

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "Executive Summary",
    "Device & Location",
    "Org & Scan Performance",
    "User Productivity",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — EXECUTIVE SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("Executive Summary")

    search = st.text_input("Search organisations", placeholder="Type an org name to filter everything below...")
    exec_org_f = org_f[org_f["org_name"].str.contains(search, case=False, na=False)] if search else org_f

    st.divider()

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Orgs",              f"{exec_org_f['org_name'].nunique()}")
    k2.metric("Total Users",       f"{exec_org_f['total_users'].sum():,}")
    k3.metric("Total Leads Added", f"{exec_org_f['total_leads_added'].sum():,}")
    k4.metric("Total Calls",       f"{exec_org_f['total_calls'].sum():,}")
    k5.metric("Total Meetings",    f"{exec_org_f['total_meetings'].sum():,}")

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        title_col, pop_col = st.columns([8, 1])
        title_col.subheader("Avg Engagement Score by Org")
        with pop_col.popover("ℹ️"):
            st.markdown(
                "**How engagement score is calculated:**\n\n"
                "| Action | Weight |\n|---|---|\n"
                "| Meetings scheduled | × 5 |\n"
                "| Leads added | × 4 |\n"
                "| Calls made | × 3 |\n"
                "| Emails sent | × 1 |\n"
                "| Tasks completed | × 1 |\n\n"
                "The chart shows the **average** of each user's daily score within the org. "
                "Orgs with only 1–2 users can look unusually high or low — always compare alongside the Users column."
            )
        fig_eng = px.bar(
            exec_org_f.sort_values("avg_engagement_score", ascending=False),
            x="org_name", y="avg_engagement_score",
            labels={"org_name": "Org", "avg_engagement_score": "Avg Engagement Score"},
            color="avg_engagement_score", color_continuous_scale="Viridis",
        )
        fig_eng.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig_eng, use_container_width=True, key="exec_engagement")

    with col_b:
        st.subheader("Total Leads Added by Org")
        fig_leads = px.bar(
            exec_org_f.sort_values("total_leads_added", ascending=False),
            x="org_name", y="total_leads_added",
            labels={"org_name": "Org", "total_leads_added": "Leads Added"},
            color="total_leads_added", color_continuous_scale="Reds",
        )
        fig_leads.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig_leads, use_container_width=True, key="exec_leads")

    st.subheader("Full Org Summary Table")
    st.caption(
        "**Conversion %** = New Leads ÷ Total Scans × 100.  "
        "**Task Completion** = Tasks Completed ÷ (Tasks Completed + Tasks Due).  "
        "**Avg Confidence** = How certain the RoloScan AI was when reading each contact — "
        "scored 0 to 1, where 1 means completely confident and lower scores mean the scan was harder to read."
    )

    display_cols = {
        "org_name":             "Org",
        "total_users":          "Users",
        "active_users":         "Active",
        "avg_engagement_score": "Avg Engagement",
        "total_leads_added":    "Leads Added",
        "total_calls":          "Calls",
        "total_emails_sent":    "Emails",
        "total_meetings":       "Meetings",
        "avg_task_completion":  "Task Completion",
        "conversion_rate_pct":  "Conversion %",
        "avg_confidence":       "Avg Confidence",
    }
    display_df = exec_org_f[list(display_cols.keys())].rename(columns=display_cols).copy()
    display_df["Avg Engagement"]  = display_df["Avg Engagement"].round(1)
    display_df["Task Completion"] = (display_df["Task Completion"] * 100).round(1).astype(str) + "%"
    display_df["Conversion %"]    = display_df["Conversion %"].round(1).astype(str) + "%"
    display_df["Avg Confidence"]  = display_df["Avg Confidence"].round(2)

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Conversion %":   st.column_config.TextColumn(
                "Conversion %",
                help="New Leads ÷ Total Scans × 100. Shows what percentage of scans resulted in a new lead.",
            ),
            "Task Completion": st.column_config.TextColumn(
                "Task Completion",
                help="Tasks Completed ÷ (Tasks Completed + Tasks Due). 100% means all due tasks were finished that day.",
            ),
            "Avg Confidence": st.column_config.NumberColumn(
                "Avg Confidence",
                help="How certain the RoloScan AI was when reading each contact — 0 to 1, where 1 = completely confident.",
            ),
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — DEVICE & LOCATION
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("Device & Location Insights")

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Users by Device Type")
        device_counts = access["device_type"].value_counts().reset_index()
        device_counts.columns = ["device_type", "count"]
        fig_device = px.pie(device_counts, names="device_type", values="count", hole=0.4)
        fig_device.update_layout(legend=dict(orientation="v", x=0.75, y=0.5, xanchor="left", yanchor="middle"))
        st.plotly_chart(fig_device, use_container_width=True, key="device_pie")

    with col_b:
        st.subheader("User Lifecycle Stages")
        st.caption(
            "Based on days since signup: New (0–7 days), Early (8–30), "
            "Growing (31–90), Mature (90+). "
            "Your dataset has no users under 33 days old, so only Growing and Mature appear — "
            "this is correct, not a display error."
        )
        stage_order = ["New (0-7d)", "Early (8-30d)", "Growing (31-90d)", "Mature (90d+)"]
        stage_counts = (
            access["user_lifecycle_stage"]
            .value_counts()
            .reindex(stage_order, fill_value=0)
            .reset_index()
        )
        stage_counts.columns = ["stage", "count"]
        fig_stage = px.bar(
            stage_counts, x="stage", y="count",
            labels={"stage": "Lifecycle Stage", "count": "Users"},
            color="stage",
            color_discrete_sequence=px.colors.sequential.Teal,
        )
        fig_stage.update_layout(showlegend=False)
        st.plotly_chart(fig_stage, use_container_width=True, key="lifecycle_bar")

    col_c, col_d = st.columns(2)

    with col_c:
        st.subheader("Top 10 States by Users")
        state_counts = access["state"].value_counts().head(10).reset_index()
        state_counts.columns = ["state", "count"]
        fig_states = px.bar(
            state_counts, x="count", y="state",
            orientation="h",
            labels={"state": "State", "count": "Users"},
            color="count", color_continuous_scale="Blues",
        )
        fig_states.update_layout(yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False)
        st.plotly_chart(fig_states, use_container_width=True, key="states_bar")

    with col_d:
        st.subheader("Operating System Breakdown")
        os_counts = access["os"].value_counts().head(8).reset_index()
        os_counts.columns = ["os", "count"]
        fig_os = px.bar(
            os_counts, x="os", y="count",
            labels={"os": "OS", "count": "Users"},
            color="count", color_continuous_scale="Oranges",
        )
        fig_os.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig_os, use_container_width=True, key="os_bar")

    st.subheader("New User Signups Over Time")
    signup_trend = access.groupby("signup_month").size().reset_index(name="signups")
    fig_signup = px.line(
        signup_trend, x="signup_month", y="signups",
        markers=True,
        labels={"signup_month": "Month", "signups": "New Users"},
    )
    st.plotly_chart(fig_signup, use_container_width=True, key="signup_trend")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — ORG & SCAN PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("Org & Scan Performance")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Scans",      f"{daily_f['total_scans'].sum():,.0f}")
    k2.metric("Total New Leads",  f"{daily_f['new_leads'].sum():,.0f}")
    k3.metric("Avg Conversion %", f"{daily_f['conversion_rate_pct'].mean():.1f}%",
              help="(New Leads ÷ Total Scans) × 100")
    k4.metric("Avg Confidence",   f"{daily_f['avg_confidence'].mean():.2f}",
              help="How certain the RoloScan AI was per scan — 0 to 1, higher is better.")

    st.divider()

    st.subheader("Scan Trend (7-Day Rolling Average)")
    st.caption(
        "Shows the smoothed daily scan volume per org. "
        "Rolling average removes day-to-day noise so trends are easier to read."
    )

    default_two = all_orgs[:2]
    trend_orgs = st.multiselect(
        "Select organisations to display on the chart",
        options=all_orgs,
        default=default_two,
        key="trend_orgs",
    )
    if not trend_orgs:
        trend_orgs = default_two

    trend_data = daily_f[daily_f["org_name"].isin(trend_orgs)].sort_values("scan_date")
    fig_trend = px.line(
        trend_data,
        x="scan_date", y="rolling_7d_avg_scans",
        color="org_name",
        labels={"scan_date": "Date", "rolling_7d_avg_scans": "Avg Scans (7-day)", "org_name": "Org"},
    )
    st.plotly_chart(fig_trend, use_container_width=True, key="scan_trend")

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Conversion Rate by Org")
        st.caption("New Leads ÷ Total Scans × 100. Higher % = more scans turning into leads.")
        conv = (
            daily_f.groupby("org_name")["conversion_rate_pct"]
            .mean().reset_index()
            .sort_values("conversion_rate_pct", ascending=False)
        )
        fig_conv = px.bar(
            conv, x="org_name", y="conversion_rate_pct",
            labels={"org_name": "Org", "conversion_rate_pct": "Avg Conversion %"},
            color="conversion_rate_pct", color_continuous_scale="Blues",
        )
        fig_conv.update_layout(showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig_conv, use_container_width=True, key="conversion_bar")

    with col_b:
        st.subheader("Scans by Day of Week")
        st.caption("Average number of scans per day of the week — shows which days are busiest.")
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        heatmap_data = (
            daily_f.groupby("day_of_week")["total_scans"]
            .mean().reindex(day_order).reset_index()
        )
        fig_dow = px.bar(
            heatmap_data, x="day_of_week", y="total_scans",
            labels={"day_of_week": "Day", "total_scans": "Avg Scans"},
            color="total_scans", color_continuous_scale="Purples",
        )
        fig_dow.update_layout(showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig_dow, use_container_width=True, key="dow_bar")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — USER PRODUCTIVITY
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.header("User Productivity")

    st.info(
        "**Engagement Score** = (Calls × 3) + (Meetings × 5) + (Emails × 1) + "
        "(Tasks Completed × 1) + (Leads Added × 4).  "
        "It is a weighted daily productivity score per user — meetings get the highest "
        "weight because they represent the most effort.",
        icon="ℹ️",
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Users",          f"{activity_f['user_id'].nunique():,}")
    k2.metric("Active User-Days",     f"{activity_f['is_active_today'].sum():,}",
              help="Count of user-days where engagement score > 0")
    k3.metric("Avg Engagement Score", f"{activity_f['engagement_score'].mean():.1f}",
              help="Mean daily engagement score across all users and days")
    k4.metric("Avg Task Completion",  f"{activity_f['task_completion_rate'].mean()*100:.1f}%",
              help="Tasks Completed ÷ (Tasks Completed + Tasks Due). 100% = all due tasks done.")

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Top 15 Users by Total Engagement Score")
        top_users = (
            activity_f.groupby(["first_name", "last_name", "org_name"])["engagement_score"]
            .sum().reset_index()
            .sort_values("engagement_score", ascending=False)
            .head(15)
        )
        top_users["name"] = top_users["first_name"] + " " + top_users["last_name"]
        fig_top = px.bar(
            top_users, x="engagement_score", y="name",
            orientation="h", color="org_name",
            labels={"engagement_score": "Total Engagement Score", "name": "User", "org_name": "Org"},
        )
        fig_top.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig_top, use_container_width=True, key="top_users")

    with col_b:
        st.subheader("Avg Daily Lead Velocity by Org")
        st.caption("Weekly leads added ÷ 7 — a comparable daily rate across orgs.")
        lead_vel = (
            activity_f.groupby("org_name")["lead_velocity_daily"]
            .mean().reset_index()
            .sort_values("lead_velocity_daily", ascending=False)
        )
        fig_vel = px.bar(
            lead_vel, x="org_name", y="lead_velocity_daily",
            labels={"org_name": "Org", "lead_velocity_daily": "Avg Leads/Day"},
            color="lead_velocity_daily", color_continuous_scale="Greens",
        )
        fig_vel.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig_vel, use_container_width=True, key="lead_velocity")
