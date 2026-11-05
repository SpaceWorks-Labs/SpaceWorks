"""Release-2 lane L25 (#163B): literal export classification of the analytics connections.

Neither row travels. A connection names a database login of THIS deployment and holds its
Metabase embed secret and the login password as ciphertext under this deployment's key; a
target space makes its own login and pastes its own secret. The platform connection is not
tenant data at all.
"""

OMITTED_MODELS = {
    "analytics.AnalyticsConnection": (
        "A deployment-local database login and Metabase secret of one space; never portable."),
    "analytics.PlatformAnalyticsConnection": (
        "The platform-wide Metabase connection of this deployment; not tenant data."),
}
