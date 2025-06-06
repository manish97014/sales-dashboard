import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import plotly.express as px

# --- Load CSV files from a given folder ---
@st.cache_data(show_spinner=False)
def load_sales_data(folder_path):
    all_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.csv'):
                all_files.append(os.path.join(root, file))
    if not all_files:
        return pd.DataFrame()

    df_list = []
    for file in all_files:
        try:
            df = pd.read_csv(file, encoding='utf-8')
            df_list.append(df)
        except Exception:
            continue

    if not df_list:
        return pd.DataFrame()

    data = pd.concat(df_list, ignore_index=True)
    return data

# --- Preprocess the sales data ---
@st.cache_data(show_spinner=False)
def preprocess_data(df):
    required_cols = ['Date', 'Tabs', 'Sale', 'Discount', 'Net Sale', 'Charges', 'Total Tax', 'Gross Amount', 'Outlet Name']
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        return pd.DataFrame()

    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date'])

    df['Year'] = df['Date'].dt.year.astype(str)
    df['Month_Num'] = df['Date'].dt.month
    df['Month'] = df['Date'].dt.month_name()
    df['Week'] = df['Date'].dt.to_period('W').apply(
        lambda r: f"{r.start_time.strftime('%d %b')} - {r.end_time.strftime('%d %b')}"
    )
    df['Week_Start'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
    df['Day'] = df['Date'].dt.strftime('%d-%b-%Y')

    df['Net Sale'] = pd.to_numeric(df['Net Sale'], errors='coerce').fillna(0)
    df['Charges'] = pd.to_numeric(df['Charges'], errors='coerce').fillna(0)
    df['Sales Value'] = df['Net Sale'] + df['Charges']

    df['Outlet Name'] = df['Outlet Name'].fillna('Unknown')
    df['Outlet Name'] = df['Outlet Name'].str.replace(r'\bNavtara\b', '', case=False, regex=True).str.strip()
    df['Tabs'] = df['Tabs'].fillna('Unknown')
    return df

# --- Get current period date range from filters ---
def get_current_period(df, selected_years, selected_months, selected_weeks, selected_days):
    df_temp = df.copy()
    if selected_years:
        df_temp = df_temp[df_temp['Year'].isin(selected_years)]
    if selected_months:
        df_temp = df_temp[df_temp['Month'].isin(selected_months)]
    if selected_weeks:
        df_temp = df_temp[df_temp['Week'].isin(selected_weeks)]
    if selected_days:
        df_temp = df_temp[df_temp['Day'].isin(selected_days)]

    if df_temp.empty:
        return None, None
    return df_temp['Date'].min(), df_temp['Date'].max()

# --- Main App ---
def main():
    st.title("📈 Sales Trends")

    folder_path = "Input files"  # Change this path as needed

    with st.spinner("Loading data..."):
        df = load_sales_data(folder_path)
    if df.empty:
        st.error("No CSV files found or data could not be loaded.")
        return

    with st.spinner("Processing data..."):
        df = preprocess_data(df)
    if df.empty:
        st.error("Required columns missing in CSV files.")
        return

    # --- Sidebar Filters ---
    st.sidebar.header("📂 Filter Data")

    years = sorted(df['Year'].unique())
    months = list(df['Month'].unique())
    outlets = sorted(df['Outlet Name'].unique())

    select_all_years = st.sidebar.checkbox("Select All Years")
    selected_years = st.sidebar.multiselect("Select Year(s):", options=years, default=years if select_all_years else [])

    select_all_months = st.sidebar.checkbox("Select All Months")
    selected_months = st.sidebar.multiselect("Select Month(s):", options=months, default=months if select_all_months else [])

    select_all_outlets = st.sidebar.checkbox("Select All Outlets")
    selected_outlets = st.sidebar.multiselect("Select Outlet(s):", options=outlets, default=outlets if select_all_outlets else [])

    df_month_filtered = df.copy()
    if selected_years:
        df_month_filtered = df_month_filtered[df_month_filtered['Year'].isin(selected_years)]
    if selected_months:
        df_month_filtered = df_month_filtered[df_month_filtered['Month'].isin(selected_months)]

    week_options = sorted(df_month_filtered['Week'].unique())
    day_options = sorted(df_month_filtered['Day'].unique())

    selected_weeks = st.sidebar.multiselect("Select Week(s):", week_options)
    selected_days = st.sidebar.multiselect("Select Date(s):", day_options)

    start_date, end_date = get_current_period(df, selected_years, selected_months, selected_weeks, selected_days)
    if start_date is None or end_date is None:
        st.warning("No data found for current filter selection.")
        return

    df_current = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]
    if selected_outlets:
        df_current = df_current[df_current['Outlet Name'].isin(selected_outlets)]

    delta_days = (end_date - start_date).days + 1
    if selected_days:
        prev_start = start_date - timedelta(days=delta_days)
        prev_end = end_date - timedelta(days=delta_days)
    elif selected_weeks:
        num_weeks = len(set(selected_weeks))
        prev_start = start_date - timedelta(weeks=num_weeks)
        prev_end = end_date - timedelta(weeks=num_weeks)
    elif selected_months:
        first_month = df_current['Date'].min().replace(day=1)
        prev_month_end = first_month - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)
        prev_start = prev_month_start
        prev_end = prev_month_end
    elif selected_years and not selected_months:
        prev_start = start_date - pd.DateOffset(years=1)
        prev_end = end_date - pd.DateOffset(years=1)
    else:
        prev_start = start_date - timedelta(days=delta_days)
        prev_end = end_date - timedelta(days=delta_days)

    df_previous = df[(df['Date'] >= prev_start) & (df['Date'] <= prev_end)]
    if selected_outlets:
        df_previous = df_previous[df_previous['Outlet Name'].isin(selected_outlets)]

    # --- KPI Cards ---
    col1, col2, col3 = st.columns(3)

    total_sales = df_current['Sales Value'].sum()
    prev_sales = df_previous['Sales Value'].sum()
    sply_start = start_date - pd.DateOffset(years=1)
    sply_end = end_date - pd.DateOffset(years=1)
    df_sply = df[(df['Date'] >= sply_start) & (df['Date'] <= sply_end)]
    if selected_outlets:
        df_sply = df_sply[df_sply['Outlet Name'].isin(selected_outlets)]
    sply_sales = df_sply['Sales Value'].sum()

    with col1:
        st.markdown("### 🟢 Current Period Sales")
        st.markdown(
            f"""
            <div style='padding:15px; border-radius:12px; background:#e6ffe6; text-align:center'>
                <h2 style='color:#008000; font-size:2.2em; margin:0;'>₹ {total_sales:,.0f}</h2>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Calculate growth % vs previous
        if prev_sales > 0:
            growth = ((total_sales - prev_sales) / prev_sales) * 100
        else:
            growth = 0
        growth_arrow = "&#9650;" if growth > 0 else "&#9660;" if growth < 0 else ""
        growth_color = "green" if growth > 0 else "red" if growth < 0 else "gray"

        # Calculate growth % vs LY
        if sply_sales > 0:
            sply_growth = ((total_sales - sply_sales) / sply_sales) * 100
        else:
            sply_growth = 0
        sply_arrow = "&#9650;" if sply_growth > 0 else "&#9660;" if sply_growth < 0 else ""
        sply_color = "green" if sply_growth > 0 else "red" if sply_growth < 0 else "gray"

        st.markdown(
            f"""
            <p style='font-size:16px; color:{growth_color}; text-align:center'>{growth_arrow} {abs(growth):.2f}% vs Previous</p>
            <p style='font-size:16px; color:{sply_color}; text-align:center'>{sply_arrow} {abs(sply_growth):.2f}% vs LY</p>
            """,
            unsafe_allow_html=True
        )

    with col2:
        st.markdown("### 🔹 Previous Period Sales")
        st.markdown(
            f"""
            <div style='padding:15px; border-radius:12px; background:#e6f0ff; text-align:center'>
                <h2 style='color:#0000CD; font-size:2.2em; margin:0;'>₹ {prev_sales:,.0f}</h2>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col3:
        st.markdown("### 🕓 Same Period LY Sales")
        st.markdown(
            f"""
            <div style='padding:15px; border-radius:12px; background:#fff0e6; text-align:center'>
                <h2 style='color:#FF8C00; font-size:2.2em; margin:0;'>₹ {sply_sales:,.0f}</h2>
            </div>
            """,
            unsafe_allow_html=True
        )

    # --- Charts ---
    tab_sales = df_current.groupby('Tabs')['Sales Value'].sum().reset_index()
    fig_tabs = px.area(tab_sales, x='Tabs', y='Sales Value', title="Sales by Tab", labels={'Tabs': 'Tab'})
    st.plotly_chart(fig_tabs, use_container_width=True)

    outlet_sales = df_current.groupby('Outlet Name')['Sales Value'].sum().reset_index()
    fig_outlets = px.bar(outlet_sales, x='Outlet Name', y='Sales Value', title="Sales by Outlet", labels={'Outlet Name': 'Outlet'})
    st.plotly_chart(fig_outlets, use_container_width=True)

# Run the app
if __name__ == "__main__":
    main()
