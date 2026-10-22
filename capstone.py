import pandas as pd
import requests
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
    y_label = "Daily reported new cases"

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
    totals = chart_data.sum()
    comparison_label = "Reported cases across the historical period"
comparison = pd.DataFrame({"Country": totals.index, "Cases": totals.values})
st.plotly_chart(px.bar(comparison, x="Country", y="Cases", color="Country",
                       title=comparison_label), use_container_width=True)

st.subheader("Population-adjusted comparison")
st.write("Cumulative reported cases per 100,000 residents (using 2022 population).")

# World Bank 2022 population data; Taiwan is not included in the World Bank API.
@st.cache_data
def load_population():
    response = requests.get(
        "https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL",
        params={"date": "2022", "format": "json", "per_page": 20000},
        timeout=30,
    )
    response.raise_for_status()
    records = response.json()[1]
    return {r["country"]["value"]: r["value"] for r in records if r["value"] is not None}

# CSSE country labels that differ from World Bank labels.
country_names = {
    "US": "United States", "Korea, South": "Korea, Rep.",
    "Russia": "Russian Federation", "Egypt": "Egypt, Arab Rep.",
    "Iran": "Iran, Islamic Rep.", "Turkey": "Turkiye",
    "Vietnam": "Viet Nam", "Slovakia": "Slovak Republic",
    "Kyrgyzstan": "Kyrgyz Republic", "Congo (Kinshasa)": "Congo, Dem. Rep.",
    "Congo (Brazzaville)": "Congo, Rep.",
}

try:
    population = load_population()
except (requests.RequestException, ValueError, IndexError, KeyError):
    population = {}
    st.warning("World Bank population data could not be loaded. Try again later.")

# Taiwan 2022 population (Taiwan Ministry of the Interior year-end figure).
population["Taiwan*"] = 23264640

rows = []
missing = []
for country in countries:
    name = country_names.get(country, country)
    pop = population.get(name)
    if pop and pop > 0:
        cases = cumulative[country].iloc[-1]
        rows.append({"Country": country, "Cases per 100,000": cases / pop * 100000})
    else:
        missing.append(country)

if rows:
    rates = pd.DataFrame(rows)
    st.plotly_chart(px.bar(rates, x="Country", y="Cases per 100,000", color="Country",
                           title="Cumulative reported cases per 100,000 population"),
                    use_container_width=True)
if missing:
    st.info("Population data unavailable for: " + ", ".join(missing) + ". These countries are omitted from the population-adjusted chart.")
st.caption("Population denominator: 2022 World Bank population indicator SP.POP.TOTL; Taiwan*: 2022 year-end population from Taiwan Ministry of the Interior (23,264,640). Rates count reported cases, not unique infected individuals; reinfections and reporting differences affect comparisons.")
st.markdown("[World Bank population data](https://data.worldbank.org/indicator/SP.POP.TOTL) · [Taiwan Ministry of the Interior](https://www.moi.gov.tw/)")

st.subheader("Explore the data")
st.dataframe(chart_data.tail(30).sort_index(ascending=False), use_container_width=True)
st.caption("Daily case counts are computed from differences in cumulative reports. Negative corrections are displayed as zero in the daily chart; this may cause summed daily counts to differ from cumulative totals.")
st.markdown("[Original CSSE data and documentation](https://github.com/CSSEGISandData/COVID-19/tree/master/csse_covid_19_data/csse_covid_19_time_series)")
