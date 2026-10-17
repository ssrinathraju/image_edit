import logging

from image_edit_server.services.email.log_sender import LogSender


def test_log_sender_logs_recipient_subject_and_body(caplog):
    with caplog.at_level(logging.INFO):
        LogSender().send("ana@example.com", "Hello", "Your code is 123456")

    assert "ana@example.com" in caplog.text
    assert "Hello" in caplog.text
    assert "Your code is 123456" in caplog.text
