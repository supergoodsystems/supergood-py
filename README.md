# This library is deprecated! 

We started off as an observability product for third-party APIs, and realized that rather than simply pointing out problems with APIs, we need to fix them. As such, we're sunsetting our pure observability product and using it internally for the new "unofficial" APIs we now generate.

Reach out to alex@supergood.ai if you'd like to learn more, or check us out at https://supergood.ai

--- 

# Python

The Supergood Python client connects Supergood to your Python application. Follow these steps to integrate with the Python client.

## 1. Install the Supergood library

```bash
pip install supergood
```

## 2. Initialize the Supergood Library

**Environment variables**

Set the environment variables `SUPERGOOD_CLIENT_ID` and `SUPERGOOD_CLIENT_SECRET` using the API keys generated in the [getting started instructions](../getting-started.md).

Initialize the Supergood client at the root of your application, or anywhere you're making API calls.

```python
from supergood import Client

Client.initialize()
```

**Passing keys**

You can also pass the API keys in manually without setting environment variables.

Replace `<CLIENT_ID>` and `<CLIENT_SECRET>` with the API keys you generated in the [getting started instructions](../getting-started.md).

```python
from supergood import Client

Client.initialize(client_id="<CLIENT_ID>", client_secret_id="<CLIENT_SECRET>")
```

Note: If your application makes use of the `multiprocessing` library to make API calls, you'll need to initialize a client for each `Process`.&#x20;

## 3. Monitor your API calls

You're all set to use Supergood!

Head back to your [dashboard](https://dashboard.supergood.ai) to start monitoring your API calls and receiving reports.

## Links

* [Supergood PyPi Project](https://pypi.org/project/supergood/)
* [Supergood\_py Source Code](https://github.com/supergoodsystems/supergood-py)
