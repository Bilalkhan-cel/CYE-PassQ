from datetime import datetime , timedelta


def slot_window(token):
    """(start, end) datetimes of the arrival slot for this token number."""
    start_time = datetime.strptime("08:00 AM", "%I:%M %p")  # starting time
    slot_duration = timedelta(minutes=20)  # each slot = 20 minSsSs
    tokens_per_slot = 35                   # about 35 tokens per slot

    # find which slot the token belongs to (slot numbers start from 0)
    slot_number = (int(token) - 1) // tokens_per_slot

    # calculate slot start and end times
    slot_start = start_time + (slot_number * slot_duration)
    slot_end = slot_start + slot_duration
    return slot_start, slot_end


def time_slot(token):
    slot_start, slot_end = slot_window(token)

    # format and return message
    return f"Please arrive between {slot_start.strftime('%I:%M %p')} & {slot_end.strftime('%I:%M %p')}"
