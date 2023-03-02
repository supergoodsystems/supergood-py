# Supergood Python Client

Monitor the usage, spend and performance of your external API's in 5 minutes flat.

1. Sign-up for an account on supergood.ai
2. Create your organization
3. Head to the "API Keys" side panel, and generate your CLIENT_ID and CLIENT_SECRET
4. In your codebase, run `pip -m install supergood`
5. Add the above CLIENT_ID and CLIENT_SECRET as environment variables in your codebase as `SUPERGOOD_CLIENT_ID` and `SUPERGOOD_CLIENT_SECRET` respectively.
6. At the top of any file you're making external API calls, add the following two lines:

```
from supergood import Client

Client()
```
... and that's it!

Head back to https://dashboard.supergood.ai to start monitoring your external API calls!
