import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="COVID-19 Global Dashboard", layout="wide")
st.title("COVID-19 Global Dashboard")
st.write("Explore historical confirmed COVID-19 cases by country using Johns Hopkins CSSE data.")

url = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv"

@st.cache_data
def load_data():
    data = pd.read_csv(url)
    dates = data.columns[4:]
    # Provinces/states are separate rows, so sum them to country totals first.
    countries = data.groupby("Country/Region")[list(dates)].sum()
    countries = countries.T
    countries.index = pd.to_datetime(countries.index, format="%m/%d/%y")
    countries = countries.sort_index()
    return countries

try:
    cumulative = load_data()
except Exception:
    st.error("Could not load the Johns Hopkins CSSE dataset. Check your internet connection and try again.")
    st.stop()

st.caption("Source: Johns Hopkins CSSE COVID-19 time-series repository. Historical reporting ends in March 2023; this is not a live COVID-19 tracker.")

countries = st.multiselect("Choose countries (add or remove as many as you like)",
                           list(cumulative.columns), default=["Taiwan*", "Japan", "US"])
view = st.radio("Case count", ["Daily new cases", "Cumulative cases"], horizontal=True)
smoothing = st.checkbox("Show 7-day moving average (daily cases only)", value=False)

if not countries:
    st.info("Select at least one country to display the chart.")
    st.stop()

if view == "Cumulative cases":
    chart_data = cumulative[countries].copy()
    y_label = "Cumulative confirmed cases"
else:
    # Daily reports are differences between successive cumulative observations.
    chart_data = cumulative[countries].diff().iloc[1:]
    # Negative values represent retrospective corrections, not negative infections.
    chart_data = chart_data.clip(lower=0)
    if smoothing:
        chart_data = chart_data.rolling(7, min_periods=1).mean()
    y_label = "Daily reported new cases" + (" (7-day average)" if smoothing else "")

plot_data = chart_data.reset_index().rename(columns={"index": "Date"})
plot_data = plot_data.melt(id_vars="Date", var_name="Country", value_name="Cases")
fig = px.line(plot_data, x="Date", y="Cases", color="Country", title=y_label,
              labels={"Cases": y_label})
fig.update_layout(hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Country comparison")
if view == "Cumulative cases":
    totals = cumulative[countries].iloc[-1]
    comparison_label = "Cumulative confirmed cases at last reporting date"
else:
    totals = chart_data.sum() if not smoothing else cumulative[countries].iloc[-1] - cumulative[countries].iloc[0]
    comparison_label = "Reported cases across the historical period"
comparison = pd.DataFrame({"Country": totals.index, "Cases": totals.values})
st.plotly_chart(px.bar(comparison, x="Country", y="Cases", color="Country",
                       title=comparison_label), use_container_width=True)

st.subheader("Explore the data")
st.dataframe(chart_data.tail(30).sort_index(ascending=False), use_container_width=True)
st.caption("Daily case counts are computed from differences in cumulative reports. Negative corrections are displayed as zero in the daily chart; this may cause summed daily counts to differ from cumulative totals. The comparison chart uses cumulative differences when a 7-day average is enabled.")
st.markdown("[Original CSSE data and documentation](https://github.com/CSSEGISandData/COVID-19/tree/master/csse_covid_19_data/csse_covid_19_time_series)")
