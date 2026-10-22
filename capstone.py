import pandas as pd
import requests
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="COVID-19 Global Dashboard", layout="wide")
st.title("COVID-19 Global Dashboard")
st.write("Explore historical COVID-19 case trends, reported case-fatality ratios, and population-adjusted trends across countries.")

base = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/"

@st.cache_data
def load_data(filename):
    data = pd.read_csv(base + filename)
    dates = data.columns[4:]
    result = data.groupby("Country/Region")[list(dates)].sum().T
    result.index = pd.to_datetime(result.index, format="%m/%d/%y")
    return result.sort_index()

@st.cache_data
def load_population():
    response = requests.get("https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL",
                            params={"date": "2022", "format": "json", "per_page": 20000}, timeout=30)
    response.raise_for_status()
    return {r["country"]["value"]: r["value"] for r in response.json()[1]
            if r["value"] is not None}

try:
    cumulative = load_data("time_series_covid19_confirmed_global.csv")
    deaths = load_data("time_series_covid19_deaths_global.csv")
except Exception:
    st.error("Unable to load the Johns Hopkins CSSE data. Please try again later.")
    st.stop()

st.caption("Source: Johns Hopkins CSSE historical time series (through March 9, 2023). Not a live tracker.")
countries = st.multiselect("Choose countries", list(cumulative.columns),
                           default=["Taiwan*", "Japan", "US"])
view = st.radio("Case count", ["Daily new cases", "Cumulative cases"], horizontal=True)
if not countries:
    st.info("Choose at least one country.")
    st.stop()

if view == "Cumulative cases":
    chart_data = cumulative[countries]
    label = "Cumulative confirmed cases"
else:
    chart_data = cumulative[countries].diff().iloc[1:].clip(lower=0)
    label = "Daily reported new cases"

st.subheader("1. COVID-19 case trends")
plot_data = chart_data.rename_axis("Date").reset_index().melt(id_vars="Date", var_name="Country", value_name="Cases")
fig = px.line(plot_data, x="Date", y="Cases", color="Country", title=label)
fig.update_layout(hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

st.subheader("2. Population-adjusted case trends")
st.write("Cases per 100,000 population over time, using 2022 population denominators.")
country_names = {"US": "United States", "Korea, South": "Korea, Rep.",
                 "Russia": "Russian Federation", "Egypt": "Egypt, Arab Rep.",
                 "Iran": "Iran, Islamic Rep.", "Turkey": "Turkiye", "Vietnam": "Viet Nam",
                 "Slovakia": "Slovak Republic", "Kyrgyzstan": "Kyrgyz Republic",
                 "Congo (Kinshasa)": "Congo, Dem. Rep.", "Congo (Brazzaville)": "Congo, Rep."}
try:
    population = load_population()
except (requests.RequestException, ValueError, IndexError, KeyError):
    population = {}
    st.warning("World Bank population data could not be loaded.")
population["Taiwan*"] = 23264640
rates = pd.DataFrame(index=chart_data.index)
missing = []
for country in countries:
    pop = population.get(country_names.get(country, country))
    if pop and pop > 0:
        rates[country] = chart_data[country] / pop * 100000
    else:
        missing.append(country)
if not rates.empty:
    rates_long = rates.rename_axis("Date").reset_index().melt(id_vars="Date", var_name="Country",
                                                               value_name="Cases per 100,000")
    fig_rates = px.line(rates_long, x="Date", y="Cases per 100,000", color="Country",
                        title=f"{view} per 100,000 population")
    fig_rates.update_layout(hovermode="x unified")
    st.plotly_chart(fig_rates, use_container_width=True)
if missing:
    st.info("Population unavailable for: " + ", ".join(missing) + ". Omitted from population-adjusted trends.")
st.caption("Population: World Bank 2022 indicator SP.POP.TOTL; Taiwan*: Taiwan Ministry of the Interior 2022 year-end population (23,264,640). "
           "Reported cases may include reinfections and are not the percentage of unique people infected.")
st.markdown("[World Bank population data](https://data.worldbank.org/indicator/SP.POP.TOTL) · [Taiwan Ministry of the Interior](https://www.moi.gov.tw/)")

st.subheader("3. Reported case-fatality ratio (CFR)")
st.write("Compare cumulative reported deaths divided by cumulative reported confirmed cases on a selected date.")
comparison_date = st.date_input("Select comparison date", value=cumulative.index.max().date(),
                                min_value=cumulative.index.min().date(), max_value=cumulative.index.max().date())
selected_date = pd.Timestamp(comparison_date)
# Dates in the source are daily, so selected_date is an exact row.
case_counts = cumulative.loc[selected_date, countries]
death_counts = deaths.loc[selected_date, countries]
rows = []
for country in countries:
    cases = case_counts[country]
    dead = death_counts[country]
    if cases > 0:
        rows.append({"Country": country, "CFR (%)": dead / cases * 100,
                     "Confirmed cases": int(cases), "Reported deaths": int(dead)})
if rows:
    cfr = pd.DataFrame(rows)
    fig_cfr = px.bar(cfr, x="Country", y="CFR (%)", color="Country",
                     hover_data=["Confirmed cases", "Reported deaths"],
                     title=f"Reported CFR on {selected_date:%Y-%m-%d}")
    st.plotly_chart(fig_cfr, use_container_width=True)
    st.dataframe(cfr, use_container_width=True, hide_index=True)
else:
    st.info("No reported confirmed cases on this date for the selected countries.")
st.caption("Reported CFR = cumulative reported deaths / cumulative confirmed cases × 100. "
           "This is not the infection-fatality ratio or an individual's risk of death. "
           "Under-ascertainment, reporting delays, age structure, and country-specific definitions limit comparisons.")

st.subheader("View Underlying Data")
st.dataframe(chart_data.tail(30).sort_index(ascending=False), use_container_width=True)
st.caption("Daily cases are differences between consecutive cumulative reports. Negative retrospective revisions are shown as zero "
           "in daily charts, so summed daily counts may differ from cumulative totals.")
st.markdown("[Johns Hopkins CSSE source and documentation](https://github.com/CSSEGISandData/COVID-19/tree/master/csse_covid_19_data/csse_covid_19_time_series)")
