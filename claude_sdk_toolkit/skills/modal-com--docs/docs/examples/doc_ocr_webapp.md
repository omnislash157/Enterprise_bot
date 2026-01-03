---
title: Serve a receipt parsing web app
url: https://modal.com/docs/examples/doc_ocr_webapp
type: examples
---

# Serve a receipt parsing web app

---

[View on GitHub](https://github.com/modal-labs/modal-examples/blob/main/09_job_queues/doc_ocr_webapp.py)

 

Copy page

# Serve a receipt parsing web app

This tutorial shows you how to use Modal to deploy a fully serverless [React](https://reactjs.org/) + [FastAPI](https://fastapi.tiangolo.com/) application.

We’re going to build a simple “Receipt Parser” web app that submits document parsing
tasks to a separate Modal app defined in [another example](https://modal.com/docs/examples/doc_ocr_jobs),
polls until the task is completed, and displays
the results. Try it out for yourself [here](https://modal-labs-examples--example-doc-ocr-webapp-wrapper.modal.run/).

It should look something like this:

[![Webapp frontend](https://modal-cdn.com/doc_ocr_frontend.jpg)](https://modal-labs-examples--example-doc-ocr-webapp-wrapper.modal.run/)

## Basic setup

Let’s get the imports out of the way and define an [`App`](https://modal.com/docs/reference/modal.App).

```shiki
from pathlib import Path

import fastapi
import fastapi.staticfiles
import modal

app = modal.App("example-doc-ocr-webapp")
```

 

Copy

Modal works with any [ASGI](https://modal.com/docs/guide/webhooks#serving-asgi-and-wsgi-apps) or [WSGI](https://modal.com/docs/guide/webhooks#wsgi) web framework. Here, we choose to use [FastAPI](https://fastapi.tiangolo.com/).

```shiki
web_app = fastapi.FastAPI()
```

 

Copy

 

## Define endpoints

We need two endpoints: one to accept an image and submit it to the Modal job queue,
and another to poll for the results of the job.

In `parse`, we’re going to submit tasks to the Function defined in the [Job
Queue tutorial](https://modal.com/docs/examples/doc_ocr_jobs), so we import it first using [`Function.lookup`](https://modal.com/docs/reference/modal.Function#lookup).

We call [`.spawn()`](https://modal.com/docs/reference/modal.Function#spawn) on the Function handle
we imported above to kick off our Function without blocking on the results. `spawn` returns
a unique ID for the function call, which we then use
to poll for its result.

```shiki
@web_app.post("/parse")
async def parse(request: fastapi.Request):
 parse_receipt = modal.Function.from_name("example-doc-ocr-jobs", "parse_document")

 form = await request.form()
 receipt = await form["receipt"].read() # type: ignore
 call = parse_receipt.spawn(receipt)
 return {"call_id": call.object_id}
```

 

Copy

`/result` uses the provided `call_id` to instantiate a `modal.FunctionCall` object, and attempt
to get its result. If the call hasn’t finished yet, we return a `202` status code, which indicates
that the server is still working on the job.

```shiki
@web_app.get("/result/{call_id}")
async def poll_results(call_id: str):
 function_call = modal.functions.FunctionCall.from_id(call_id)
 try:
 result = function_call.get(timeout=0)
 except TimeoutError:
 return fastapi.responses.JSONResponse(content="", status_code=202)

 return result
```

 

Copy

Now that we’ve defined our endpoints, we’re ready to host them on Modal.
First, we specify our dependencies — here, a basic Debian Linux
environment with FastAPI installed.

```shiki
image = modal.Image.debian_slim(python_version="3.12").uv_pip_install(
 "fastapi[standard]==0.115.4"
)
```

 

Copy

Then, we add the static files for our front-end. We’ve made [a simple React
app](https://github.com/modal-labs/modal-examples/tree/main/09_job_queues/doc_ocr_frontend) that hits the two endpoints defined above. To package these files with our app, we use `add_local_dir` with the local directory of the assets, and specify that we want them
in the `/assets` directory inside our container (the `remote_path`). Then, we instruct FastAPI to [serve
this static file directory](https://fastapi.tiangolo.com/tutorial/static-files/) at our root path.

```shiki
local_assets_path = Path(__file__).parent / "doc_ocr_frontend"
image = image.add_local_dir(local_assets_path, remote_path="/assets")
```

 

Copy

We serve them from our FastAPI app as `StaticFiles`.

To put our FastAPI app on Modal, we need to return it from a Python function
that is wrapped with some extra decorators:

- [`modal.asgi_app`](https://modal.com/docs/reference/modal.asgi_app) to ensure the Modal system knows to route web traffic to it (and in what format)
- [`modal.concurrent`](https://modal.com/docs/reference/modal.concurrent) to allow more than one request (e.g. for stylesheet and for HTML) to be served concurrently
- [`app.function`](https://modal.com/docs/reference/modal.App#function) to turn our Python function into a Modal Function and define the infrastructure it needs
 (here, just the dependencies).

```shiki
@app.function(image=image)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def wrapper():
 web_app.mount("/", fastapi.staticfiles.StaticFiles(directory="/assets", html=True))
 return web_app
```

 

Copy

 

## Running

While developing, you can run this as an ephemeral app by executing the command

```shiki
modal serve doc_ocr_webapp.py
```

 

Copy

If successful, this will print a URL for your app that you can navigate to in
your browser 🎉 .

The result should look something like this:

[![Webapp frontend](https://modal-cdn.com/doc_ocr_frontend.jpg)](https://modal-labs-examples--example-doc-ocr-webapp-wrapper.modal.run/)

Modal watches all the mounted files and updates the app if anything changes.
See [these docs](https://modal.com/docs/guide/webhooks#developing-with-modal-serve) for more details.

## Deploy

To deploy your application, run

```shiki
modal deploy doc_ocr_webapp.py
```

 

Copy

That’s all!

[Serve a receipt parsing web app](#serve-a-receipt-parsing-web-app)[Basic setup](#basic-setup)[Define endpoints](#define-endpoints)[Running](#running)[Deploy](#deploy)

 

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
modal serve 09_job_queues/doc_ocr_webapp.py
```

 

Copy
