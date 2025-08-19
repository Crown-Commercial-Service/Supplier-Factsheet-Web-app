from flask import Flask, request, render_template, Response
import pandas as pd
import requests
from pandas import json_normalize
import datetime
from bs4 import BeautifulSoup
from datetime import date, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
app = Flask(__name__)

def search_organization(name, duns, country_code, company_no):
    """ This function searches for an organization by its name,duns,country code and company no.
        and will output a table which will be given to the web page to display.

    :param name(string): name of the organization
    :param duns(string): duns number of the organization :
    :param country_code(string): country code of the organization :
    :param company_no(string): company number of the organization :
    :return:
        dataframe containing information about the organization
    """
    try:
        payload = {
            "requestType": "SearchOrganisation",
            "parameters": {
                "name": name,
                "dunsNumber": duns,
                "country": country_code,
                "state": "",
                "CompaniesHouseNumber": company_no,
                "OnDemandChecks": "true"
            }
        }
        url = "https://prod-25.uksouth.logic.azure.com:443/workflows/5319fad3d7e341a89183b32df72671ba/triggers/manual/paths/invoke?api-version=2016-10-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=bzgkWjBp4_GTsfJ6A7-YBsFiZCT2DfIf1L43ZxNU4MM"
        response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload)
        data = response.json()
        # Convert response to DataFrame
        df = pd.DataFrame(data.get("searchOrganisation", []))
        return df
    except Exception as e:
        print(f"Error: {e}")
        return pd.DataFrame()


def failureScore(duns):
  """ This function returns the failure score of the organization.

  :param duns(string): duns number of the organization :
  :return:
  dataframe containing failure score information about the organization
  """
  url = 'https://prod-03.uksouth.logic.azure.com:443/workflows/fad7fbb09c4b4c16b5c4abcb3af3b75d/triggers/manual/paths/invoke?api-version=2016-10-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=Lilvq4QtOJeawHR9OK9cbQnjWlFddjzMvI-4nJNusVE'
  headers = {'Content-Type': 'application/json'}

  payload = {
      "Account": [{
          "DunsNumber": duns.strip(),
          "OnDemandChecks": "true",
          "PartOfDailyChecks": "false"
      }]
  }

  response = requests.post(url, headers=headers, json=payload)
  if response.status_code != 200:
    print("Error retrieving data. Please try again.")
    df = pd.DataFrame()
    # org_df = search_organization('', duns.strip(), '', '')
    return df

  data = response.json()

  df = json_normalize(data)
  if df.empty:
    df = pd.DataFrame()
    # org_df = search_organization('', duns.strip(), '', '')
    return df

  df = df.rename(columns={"Failure_Score_National_Percentile__c": "Failure score",
                          "Latest_Financials_Quick_Ratio__c": "Quick ratio",
                          "Latest_Financials_Net_Worth__c": "Net worth",
                          "Latest_Financials_Sales_Revenue__c": "Sales Revenue",
                          "Latest_Financials_Operating_Profit__c": "Operating Profit",
                          "Latest_Financials_Retained_Earnings__c": "Retained Earnings",
                          "Employee_Quantity_Value__c": "Number of Employees" })
  df = df [["Name", "Failure score", "Quick ratio","Net worth", "Sales Revenue","Operating Profit", "Retained Earnings","Number of Employees"]]
  # org_df = search_organization('', duns.strip(), '', '')
  return df


def search_google_news(Company_name, num_results=10, time_period_months=12):
    """
    This function retrieves information online about a company.

    :param Company_name(string): name of the company:
    :param num_results(integer): number of results to return:
    :param time_period_months(integer): number of months to return:
    :return:
        dataframe containing online information about the company
    """
    Company_name = Company_name.replace(' ', '+')
    start_date = (datetime.datetime.now() - timedelta(days=time_period_months * 30)).strftime('%Y-%m-%d')
    url = f"https://news.google.com/rss/search?q={Company_name}"

    try:
        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item')

        news_items = [
            {
                'Title': item.title.text,
                'Article Links': item.link.text,
                'Publish Date': datetime.datetime.strptime(item.pubDate.text, '%a, %d %b %Y %H:%M:%S %Z')
            }
            for item in items[:num_results]
        ]

        df = pd.DataFrame(news_items)
        df['Article Links'] = df.apply(lambda row: f'<a href="{row["Article Links"]}">{row["Title"]}</a>', axis=1)

        # Return safe HTML string for your template
        return df[['Article Links', 'Publish Date']].to_html(escape=False, index=False, classes="professional-table")

    except requests.exceptions.RequestException as e:
        print(f"Error fetching news: {e}")
        return "<p>No news available.</p>"



# Function to fetch key people
def key_people(company_number):
    """
    This function retrieves information about key people of the company.
    :param company_number(string): company house number of the company:
    :return:
    dataframe containing key people information about the company
    """

    # Return an empty DataFrame if company_number is None or invalid
    if company_number is None or pd.isna(company_number):
      return pd.DataFrame()

    # Construct the API request
    url = f"https://api.company-information.service.gov.uk/company/{company_number}/officers"
    compnayhouse_API_key = 'a17ad3d4-ee27-4301-a84f-8e0970a1b3b4'
    headers = {'Authorization': compnayhouse_API_key}

    try:
        # Make the API request
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Parse the response JSON
        data = response.json()
        if 'items' not in data:
            # If 'items' key is missing, return an empty DataFrame
            return pd.DataFrame()

        # Normalize the JSON data into a DataFrame
        officer_df = json_normalize(data, record_path=['items']).rename(columns={
            'appointed_on': 'Date of Appointment',
            'country_of_residence': 'Country of Residence',
            'name': 'Name',
            'nationality': 'Nationality',
            'occupation': 'Occupation'
        })

        # If the DataFrame is empty, return it
        if officer_df.empty:
            return pd.DataFrame()

        # Select relevant columns
        officer_df = officer_df[['Date of Appointment', 'Name', 'Country of Residence', 'Nationality', 'Occupation']]
        return officer_df

    except requests.exceptions.RequestException as e:
        # Handle request exceptions (e.g., connection errors)
        print(f"Error fetching key people: {e}")
        return pd.DataFrame()
    except ValueError as e:
        # Handle JSON parsing errors
        print(f"Error parsing response JSON: {e}")
        return pd.DataFrame()

def get_options_and_dropdown(company_name):
  """
  This function retrieves information about options and dropdown of the company.

  :param company_name(string): name of the company:
  :return:
  dataframe containing dropdown options of the company that would be used for the graphing
  """

  alpha_API_key = '7LOX5ZRD7Q04IF25' # currently API key needs to be changed to better one that gives unlimited use
  name_search = f'https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={company_name}&apikey={alpha_API_key}'
  response = requests.get(name_search)
  data = response.json()
  if 'bestMatches' in data and data['bestMatches']:
    df = pd.json_normalize(data, record_path=['bestMatches'])
    options = df['1. symbol'].tolist()
    options = [ str(x).split('.')[0] if '.' in str(x) else str(x) for x in options]

    return options

  else:

    print(f"No matches found for company name: {company_name}")
    return None


def graph(selected_symbol):
    """
    This function displays the graph of the company based on selected option derived
    from get_options_and_dropdown function.
    :param selected_symbol:
    :return:
     matplotlib graph which is passed to the base.html page
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=365)
    end_date_str = end_date.strftime('%Y-%m-%d')
    start_date_str = start_date.strftime('%Y-%m-%d')

    # Fetch stock market data from API
    graph_API_key = 'fd6da8697b5c42e7804695f4861f21af'
    graph_url = f'https://api.twelvedata.com/time_series?symbol={selected_symbol}&interval=1day&apikey={graph_API_key}&timezone=Europe%2FLondon&outputsize=5000&start_date={start_date_str}&end_date={end_date_str}'
    response = requests.get(graph_url)
    graph_data = response.json()

    if 'values' in graph_data:
        df_graph = pd.DataFrame(graph_data['values'])
        df_graph['datetime'] = pd.to_datetime(df_graph['datetime'])
        df_graph = df_graph.set_index('datetime')
        df_graph['close'] = pd.to_numeric(df_graph['close'], errors='coerce')

        min_price = df_graph['close'].min()
        max_price = df_graph['close'].max()
        min_date = df_graph['close'].idxmin()
        max_date = df_graph['close'].idxmax()

        plt.clf()  # Clear the previous plot
        plt.plot(df_graph.index, df_graph['close'], color='black')
        plt.title(f'Stock Price of {selected_symbol}')
        plt.xlabel('Date')
        plt.ylabel('Close Price')
        plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.gcf().autofmt_xdate()
        plt.xticks(rotation=45)
        plt.plot(min_date, min_price, marker='o', markersize=4, color='red', label='Minimum Close')
        plt.plot(max_date, max_price, marker='o', markersize=4, color='green', label='Maximum Close')

        y_offset = 0.04 * (plt.ylim()[1] - plt.ylim()[0])
        plt.text(min_date, min_price + y_offset, f'Min={min_price:.2f}', color='black',
                 horizontalalignment='center', verticalalignment='bottom',
                 bbox=dict(facecolor='white', edgecolor='none', pad=1))
        plt.text(max_date, max_price - y_offset, f'Max={max_price:.2f}', color='black',
                 horizontalalignment='center', verticalalignment='top',
                 bbox=dict(facecolor='white', edgecolor='none', pad=1))

        plt.legend()
        plt.tight_layout()

        # Save plot to BytesIO
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()  # close figure
        buf.seek(0)
        return buf.read()  # return raw bytes
    else:
        # Handle API error or no data
        plt.clf()
        plt.text(0.5, 0.5, 'No data available', ha='center', va='center')
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        buf.seek(0)
        return buf.read()


@app.route('/plot/<symbol>')
def plot_graph(symbol):
    """
    This function displays the graph of the company based on selected option and display it on webpage.
    :param symbol(string): option chosen from dropdown list
    :return:
    """
    graph_img = graph(symbol)
    return Response(graph_img, mimetype='image/png')
@app.route('/', methods=['GET', 'POST'])
def index():
    """
    This function displays the main page of the application.
    """
    org_table = ""
    failurescore_table = ""
    news_html= ""
    message = ""
    key_people_table = ""
    company_no =""
    stock_options = ""
    selected_symbol = ""
    if request.method == 'POST':
        name = request.form.get('entityName')
        duns = request.form.get('duns1')
        country_code = request.form.get('countryCode')
        company_no = request.form.get('companyNo')
        df = search_organization(name, duns, country_code, company_no)

        if len(name) == 0 and len(company_no) == 0 and len(country_code) == 0 and len(duns) > 0:
            name = df['Name'].iloc[0]
            country_code = df['BillingCountryCode'].iloc[0]
            company_no = df['CompaniesHouseNumber'].iloc[0]

        if len(name) == 0 and len(country_code) == 0 and len(company_no) > 0 and len(duns) > 0:
            import sys
            print("here", file=sys.stderr)
            name = df['Name'].iloc[0]
            country_code = df['BillingCountryCode'].iloc[0]
            company_no = df['CompaniesHouseNumber'].iloc[0]

        failurescore_df = failureScore(str(duns))
        news_html = search_google_news(name)
        key_people_df= key_people(company_no)
        stock_options = get_options_and_dropdown(name)
        selected_symbol = stock_options[0] if stock_options else ''
        if not df.empty:
            org_table = df.to_html(classes="custom-table", index=False)
            failurescore_table = failurescore_df.to_html(classes="custom-table", index=False)
            key_people_table =key_people_df.to_html(classes="custom-table", index=False)

        else:
            if len(name) == 0 and len(country_code) == 0 and len(duns) == 0 and len(company_no) > 0:
                message = f"No data found for {company_no} please provide more information"
            else:
                message = "Organisation not found"


    return render_template('base.html', message=message,
                           org_table=org_table, failurescore_table=failurescore_table,
                           news_html=news_html,company_no=company_no,
                           key_people_table=key_people_table,
                           stock_options=stock_options,
                           selected_symbol=selected_symbol)



if __name__ == '__main__':
    app.run(debug=True)

    # search_organization(name="TESCO PLC", duns=216854067, country_code="GB", company_no="00445790")
    # todo when only company name is giving solve this