from cloud_build_status.event import Event, IrrelevantEvent
from cloud_build_status.provider import Provider


def build_status(event, context):
    """
    Background Cloud Function to be triggered by Pub/Sub.

    Updates repository build status. Triggered by incoming
    pubsub messages from Google Cloud Build.
    """

    try:
        event = Event(event)
        provider = Provider.create_from_event(event)
    except IrrelevantEvent:
        print(RuntimeError('Ignoring Cloud Build event because ' \
                'it is not related to a mirrored repository'))
    else:
        provider.send_status()

    return "OK"
