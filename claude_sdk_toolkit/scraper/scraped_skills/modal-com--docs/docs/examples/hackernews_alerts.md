---
title: Run cron jobs in the cloud to search Hacker News
url: https://modal.com/docs/examples/hackernews_alerts
type: examples
---

# Run cron jobs in the cloud to search Hacker News

---

[View on GitHub](https://github.com/modal-labs/modal-examples/blob/main/05_scheduling/hackernews_alerts.py)

 

Copy page

# Run cron jobs in the cloud to search Hacker News

In this example, we use Modal to deploy a cron job that periodically queries Hacker News for
new posts matching a given search term, and posts the results to Slack.

## Import and define the app

Let’s start off with imports, and defining a Modal app.

```shiki
import os
from datetime import datetime, timedelta

import modal

app = modal.App("example-hackernews-alerts")
```

 

Copy

Now, let’s define an image that has the `slack-sdk` package installed, in which we can run a function
that posts a slack message.

```shiki
slack_sdk_image = modal.Image.debian_slim().uv_pip_install("slack-sdk")
```

 

Copy

 

## Defining the function and importing the secret

Our Slack bot will need access to a bot token.
We can use Modal’s [Secrets](https://modal.com/secrets) interface to accomplish this.
To quickly create a Slack bot secret, click the “Create new secret” button.
Then, select the Slack secret template from the list options,
and follow the instructions in the “Where to find the credentials?” panel.
Name your secret `hn-bot-slack.`

Now, we define the function `post_to_slack`, which simply instantiates the Slack client using our token,
and then uses it to post a message to a given channel name.

```shiki
@app.function(
 image=slack_sdk_image,
 secrets=[modal.Secret.from_name("hn-bot-slack", required_keys=["SLACK_BOT_TOKEN"])],
)
async def post_to_slack(message: str):
 import slack_sdk

 client = slack_sdk.WebClient(token=os.environ["SLACK_BOT_TOKEN"])
 client.chat_postMessage(channel="hn-alerts", text=message)
```

 

Copy

 

## Searching Hacker News

We are going to use Algolia’s [Hacker News Search API](https://hn.algolia.com/api) to query for posts
matching a given search term in the past X days. Let’s define our search term and query period.

```shiki
QUERY = "serverless"
WINDOW_SIZE_DAYS = 1
```

 

Copy

Let’s also define an image that has the `requests` package installed, so we can query the API.

```shiki
requests_image = modal.Image.debian_slim().uv_pip_install("requests")
```

 

Copy

We can now define our main entrypoint, that queries Algolia for the term, and calls `post_to_slack` on all the results. We specify a [schedule](https://modal.com/docs/guide/cron) in the function decorator, which means that our function will run automatically at the given interval.

```shiki
@app.function(image=requests_image)
def search_hackernews():
 import requests

 url = "http://hn.algolia.com/api/v1/search"

 threshold = datetime.utcnow() - timedelta(days=WINDOW_SIZE_DAYS)

 params = {
 "query": QUERY,
 "numericFilters": f"created_at_i>{threshold.timestamp()}",
 }

 response = requests.get(url, params, timeout=10).json()
 urls = [item["url"] for item in response["hits"] if item.get("url")]

 print(f"Query returned {len(urls)} items.")

 post_to_slack.for_each(urls)
```

 

Copy

 

## Test running

We can now test run our scheduled function as follows: `modal run hackernews_alerts.py::app.search_hackernews`

## Defining the schedule and deploying

Let’s define a function that will be called by Modal every day

```shiki
@app.function(schedule=modal.Period(days=1))
def run_daily():
 search_hackernews.remote()
```

 

Copy

In order to deploy this as a persistent cron job, you can run `modal deploy hackernews_alerts.py`,

Once the job is deployed, visit the [apps page](https://modal.com/apps) page to see
its execution history, logs and other stats.

[Run cron jobs in the cloud to search Hacker News](#run-cron-jobs-in-the-cloud-to-search-hacker-news)[Import and define the app](#import-and-define-the-app)[Defining the function and importing the secret](#defining-the-function-and-importing-the-secret)[Searching Hacker News](#searching-hacker-news)[Test running](#test-running)[Defining the schedule and deploying](#defining-the-schedule-and-deploying)

 

## Try this on Modal!

You can run this example on Modal in 60 seconds.

[Create account to run](/signup)

After creating a free account, install the Modal Python package, and
create an API token.

$

```shiki
pip install modal
```

$

```shiki
modal setup
```

 

Copy

Clone the [modal-examples](https://github.com/modal-labs/modal-examples) repository and run:

$

```shiki
git clone https://github.com/modal-labs/modal-examples
```

$

```shiki
cd modal-examples
```

$

```shiki
modal run 05_scheduling/hackernews_alerts.py
```

 

Copy
