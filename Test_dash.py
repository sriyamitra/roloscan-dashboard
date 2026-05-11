"""
analytics_preprocessing.py
============================
This script loads, cleans, joins, and enriches three CSV datasets:
  1. Daily Analytics     → scan-level performance per org per day
  2. Generated Access    → user device/location metadata
  3. User Activity       → per-user daily activity metrics

The output is a set of clean, analysis-ready CSVs that can be imported
directly into Tableau or Power BI for visualization.

Requirements:
    pip install pandas numpy
"""

import pandas as pd
import numpy as np
import os

# ──────────────────────────────────────────────
# CONFIGURATION — update these paths as needed
# ──────────────────────────────────────────────

DAILY_ANALYTICS_PATH  = "ucd_data_rolo_generated_daily_analytics.csv"
GENERATED_ACCESS_PATH = "ucd_data_rolo_generated_access_data.csv"
USER_ACTIVITY_PATH    = "ucd_data_rolo_generated_user_activity.csv"
OUTPUT_DIR            = "output"  # folder where clean CSVs will be saved

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ══════════════════════════════════════════════
# SECTION 1: LOAD DATA
# ══════════════════════════════════════════════

print("📂 Loading data...")

daily   = pd.read_csv(DAILY_ANALYTICS_PATH)
access  = pd.read_csv(GENERATED_ACCESS_PATH)
activity = pd.read_csv(USER_ACTIVITY_PATH)

print(f"  ✅ Daily Analytics:  {daily.shape[0]:,} rows")
print(f"  ✅ Generated Access: {access.shape[0]:,} rows")
print(f"  ✅ User Activity:    {activity.shape[0]:,} rows")


# ══════════════════════════════════════════════
# SECTION 2: CLEAN & PARSE DATES
# ══════════════════════════════════════════════

print("\n🧹 Cleaning data...")

# Parse date columns to proper datetime types
# This is essential for time-series charts in Tableau/Power BI
daily["scan_date"]       = pd.to_datetime(daily["scan_date"])
access["signup_date"]    = pd.to_datetime(access["signup_date"])
activity["summary_date"] = pd.to_datetime(activity["summary_date"])

# Strip leading/trailing whitespace from string columns
# Prevents invisible mismatches when joining on org_name or user_id
daily["org_name"]    = daily["org_name"].str.strip()
activity["org_name"] = activity["org_name"].str.strip()

# Standardise user_id type to string in both tables
# Avoids silent join failures when one table has int and other has str
access["user_id"]   = access["user_id"].astype(str).str.strip()
activity["user_id"] = activity["user_id"].astype(str).str.strip()

# Fill numeric NaN values with 0 (missing activity = no activity)
activity_numeric_cols = [
    "leads_added_today", "leads_added_week", "leads_added_month",
    "total_leads_created", "calls_made_today", "emails_sent_today",
    "meetings_scheduled_today", "leads_contacted_today",
    "tasks_completed_today", "tasks_due_today", "total_pending_tasks"
]
activity[activity_numeric_cols] = activity[activity_numeric_cols].fillna(0)

daily["total_scans"]         = daily["total_scans"].fillna(0)
daily["new_leads"]           = daily["new_leads"].fillna(0)
daily["avg_confidence"]      = daily["avg_confidence"].fillna(0)
daily["avg_processing_time"] = daily["avg_processing_time"].fillna(0)


# ══════════════════════════════════════════════
# SECTION 3: DAILY ANALYTICS — DERIVED METRICS
# ══════════════════════════════════════════════

print("\n📊 Computing Daily Analytics metrics...")

# --- Conversion Rate ---
# What percentage of scans actually resulted in a new lead?
# Clamped to [0, 100] to guard against data anomalies
daily["conversion_rate_pct"] = np.where(
    daily["total_scans"] > 0,
    (daily["new_leads"] / daily["total_scans"] * 100).clip(0, 100),
    0
)

# --- 7-Day Rolling Average of Scans (per org) ---
# Smooths out day-to-day noise so trends are visible in line charts
daily = daily.sort_values(["org_name", "scan_date"])
daily["rolling_7d_avg_scans"] = (
    daily.groupby("org_name")["total_scans"]
    .transform(lambda x: x.rolling(7, min_periods=1).mean())
)

# --- Week-over-Week scan growth (%) ---
# Compares this week's scans to the same day 7 days ago, per org
daily["scans_wow_growth_pct"] = (
    daily.groupby("org_name")["total_scans"]
    .transform(lambda x: x.pct_change(periods=7) * 100)
)

# --- Processing Efficiency Flag ---
# Flags rows where processing time is above the 75th percentile
# Useful for highlighting performance outliers in dashboards
p75_proc_time = daily["avg_processing_time"].quantile(0.75)
daily["is_slow_processing"] = daily["avg_processing_time"] > p75_proc_time

# --- Day of Week (for heatmap analysis) ---
daily["day_of_week"]     = daily["scan_date"].dt.day_name()
daily["day_of_week_num"] = daily["scan_date"].dt.dayofweek  # 0=Mon, 6=Sun
daily["week_number"]     = daily["scan_date"].dt.isocalendar().week.astype(int)
daily["year_month"]      = daily["scan_date"].dt.to_period("M").astype(str)

# Save enriched daily analytics
daily.to_csv(f"{OUTPUT_DIR}/daily_analytics_enriched.csv", index=False)
print(f"  ✅ Saved: {OUTPUT_DIR}/daily_analytics_enriched.csv")


# ══════════════════════════════════════════════
# SECTION 4: USER ACTIVITY — DERIVED METRICS
# ══════════════════════════════════════════════

print("\n👤 Computing User Activity metrics...")

# --- Task Completion Rate ---
# Ratio of tasks completed vs total due today
# Gives a daily productivity score per user
activity["task_completion_rate"] = np.where(
    (activity["tasks_completed_today"] + activity["tasks_due_today"]) > 0,
    activity["tasks_completed_today"] /
    (activity["tasks_completed_today"] + activity["tasks_due_today"]),
    0
)

# --- Lead Velocity (daily rate from weekly figure) ---
# Converts weekly leads to an average daily rate for comparable trending
activity["lead_velocity_daily"] = activity["leads_added_week"] / 7

# --- Composite Engagement Score ---
# Weighted sum of all outbound/productive activities.
# Weights reflect relative effort/impact of each action — adjust as needed.
activity["engagement_score"] = (
    activity["calls_made_today"]          * 3 +
    activity["meetings_scheduled_today"]  * 5 +
    activity["emails_sent_today"]         * 1 +
    activity["tasks_completed_today"]     * 1 +
    activity["leads_added_today"]         * 4
)

# --- Active vs Dormant Flag ---
# A user with zero score on a given day is flagged as dormant
# Useful for churn analysis and re-engagement targeting
activity["is_active_today"] = activity["engagement_score"] > 0

# --- User Rank by Engagement (per day) ---
# Ranks users within each summary_date — powers leaderboard visuals
activity["daily_engagement_rank"] = (
    activity.groupby("summary_date")["engagement_score"]
    .rank(ascending=False, method="min")
)

# --- Add time dimensions for slicing ---
activity["week_number"] = activity["summary_date"].dt.isocalendar().week.astype(int)
activity["year_month"]  = activity["summary_date"].dt.to_period("M").astype(str)

# Save enriched user activity
activity.to_csv(f"{OUTPUT_DIR}/user_activity_enriched.csv", index=False)
print(f"  ✅ Saved: {OUTPUT_DIR}/user_activity_enriched.csv")


# ══════════════════════════════════════════════
# SECTION 5: ACCESS DATA — CLEAN & ENRICH
# ══════════════════════════════════════════════

print("\n📱 Processing Access / Device data...")

# Standardise categorical fields for consistent grouping in charts
access["device_type"] = access["device_type"].str.strip().str.title()  # e.g. "mobile" → "Mobile"
access["os"]          = access["os"].str.strip()
access["browser"]     = access["browser"].str.strip()
access["city"]        = access["city"].str.strip().str.title()
access["state"]       = access["state"].str.strip().str.upper()  # e.g. "ca" → "CA"

# --- Cohort Month (for signup trend analysis) ---
# Groups users by their signup month — useful for monthly cohort charts
access["signup_month"] = access["signup_date"].dt.to_period("M").astype(str)

# --- Days Since Signup ---
# Useful for segmenting users by lifecycle stage (new / growing / mature)
today = pd.Timestamp("today").normalize()
access["days_since_signup"] = (today - access["signup_date"]).dt.days

access["user_lifecycle_stage"] = pd.cut(
    access["days_since_signup"],
    bins=[-1, 7, 30, 90, float("inf")],
    labels=["New (0-7d)", "Early (8-30d)", "Growing (31-90d)", "Mature (90d+)"]
)

# Save enriched access data
access.to_csv(f"{OUTPUT_DIR}/access_enriched.csv", index=False)
print(f"  ✅ Saved: {OUTPUT_DIR}/access_enriched.csv")


# ══════════════════════════════════════════════
# SECTION 6: JOIN — Activity + Access
# ══════════════════════════════════════════════

print("\n🔗 Joining User Activity with Access data...")

# Left join: keep all activity rows, enrich with device/location info
# Users in activity but not in access will have NaN for access columns
activity_with_access = activity.merge(
    access[[
        "user_id", "device_type", "os", "browser", "app_version",
        "city", "state", "signup_date", "signup_month",
        "days_since_signup", "user_lifecycle_stage"
    ]],
    on="user_id",
    how="left"
)

# Save the joined table
activity_with_access.to_csv(f"{OUTPUT_DIR}/activity_with_access.csv", index=False)
print(f"  ✅ Saved: {OUTPUT_DIR}/activity_with_access.csv")


# ══════════════════════════════════════════════
# SECTION 7: ORG-LEVEL SUMMARY TABLE
# ══════════════════════════════════════════════

print("\n🏢 Building Org-level summary...")

# Aggregate user activity to org level for executive/org-wide dashboards
org_activity_summary = activity.groupby("org_name").agg(
    total_users            = ("user_id", "nunique"),
    active_users           = ("is_active_today", "sum"),
    avg_engagement_score   = ("engagement_score", "mean"),
    total_leads_added      = ("leads_added_today", "sum"),
    total_calls            = ("calls_made_today", "sum"),
    total_emails_sent      = ("emails_sent_today", "sum"),
    total_meetings         = ("meetings_scheduled_today", "sum"),
    avg_task_completion    = ("task_completion_rate", "mean"),
    total_pending_tasks    = ("total_pending_tasks", "sum"),
).reset_index()

# Merge with daily analytics summary (latest scan stats per org)
latest_daily = daily.sort_values("scan_date").groupby("org_name").last().reset_index()
latest_daily = latest_daily[[
    "org_name", "total_scans", "new_leads",
    "conversion_rate_pct", "avg_confidence", "avg_processing_time"
]]

org_summary = org_activity_summary.merge(latest_daily, on="org_name", how="left")

org_summary.to_csv(f"{OUTPUT_DIR}/org_summary.csv", index=False)
print(f"  ✅ Saved: {OUTPUT_DIR}/org_summary.csv")


# ══════════════════════════════════════════════
# SECTION 8: FINAL SUMMARY PRINT
# ══════════════════════════════════════════════

print("\n" + "═" * 50)
print("✅ All outputs saved to:", OUTPUT_DIR)
print("═" * 50)
print("\nFiles ready for Tableau / Power BI:")
print(f"  📄 daily_analytics_enriched.csv  → Dashboard 1: Org/Scan Performance")
print(f"  📄 user_activity_enriched.csv    → Dashboard 2: User Productivity")
print(f"  📄 access_enriched.csv           → Dashboard 3: Device & Geo Insights")
print(f"  📄 activity_with_access.csv      → Combined: Activity + Device/Geo")
print(f"  📄 org_summary.csv               → Executive Summary view")

print("""
──────────────────────────────────────────────
NEXT STEPS IN TABLEAU / POWER BI:
──────────────────────────────────────────────
1. Load all CSVs as separate data sources
2. Create relationships:
     org_summary  ←→ daily_analytics_enriched  (on org_name)
     org_summary  ←→  user_activity_enriched   (on org_name)
     activity_with_access ←→ access_enriched   (on user_id)
3. Build dashboards using the enriched columns
   (conversion_rate_pct, engagement_score, etc.)
""")