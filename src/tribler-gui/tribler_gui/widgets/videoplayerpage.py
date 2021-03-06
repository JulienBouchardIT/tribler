import os
import sys

from PyQt5.QtCore import QEvent, QTimer, Qt
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QWidget

from tribler_gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import format_speed, get_image_path, seconds_to_string


class VideoPlayerPage(QWidget):
    """
    This class manages the video player and all controls on the page.
    """

    def __init__(self):
        QWidget.__init__(self)

        self.video_player_port = None
        self.video_player_api_key = None
        self.active_infohash = ""
        self.active_index = -1
        self.media = None
        self.mediaplayer = None
        self.instance = None
        self.manager = None
        self.play_icon = None
        self.pause_icon = None
        self.stop_icon = None
        self.volume_on_icon = None
        self.volume_off_icon = None
        self.update_timer = None
        self.freeze = False
        self.prebuf = 0
        self.headerbuf = 0
        self.footerbuf = 0
        self.buffering = False
        self.filename = ""

    def initialize_player(self):
        # TODO: We disabled VLC loading for the moment being, due to a crash when parsing media.
        # Also see issue #5483.
        vlc_available = False
        vlc = None
        # try:
        #     from tribler_gui import vlc
        # except OSError:
        #     vlc_available = False

        if vlc and vlc.plugin_path:
            os.environ['VLC_PLUGIN_PATH'] = vlc.plugin_path

        if not vlc_available:
            self.window().vlc_available = False
            self.window().left_menu_button_video_player.setHidden(True)
            return

        self.instance = vlc.Instance()
        if not self.instance:
            self.window().vlc_available = False
            self.window().left_menu_button_video_player.setHidden(True)
            return

        self.mediaplayer = self.instance.media_player_new()
        self.window().video_player_widget.should_hide_video_widgets.connect(self.hide_video_widgets)
        self.window().video_player_widget.should_show_video_widgets.connect(self.show_video_widgets)
        # self.window().video_player_position_slider.should_change_video_position.connect(
        #    self.on_should_change_video_time
        # )
        self.window().video_player_volume_slider.valueChanged.connect(self.on_volume_change)
        self.window().video_player_volume_slider.setValue(self.mediaplayer.audio_get_volume())
        self.window().video_player_volume_slider.setFixedWidth(0)

        self.window().video_player_play_pause_button.clicked.connect(self.on_play_pause_button_click)
        self.window().video_player_stop_button.clicked.connect(self.on_stop_button_click)
        self.window().video_player_volume_button.clicked.connect(self.on_volume_button_click)
        self.window().video_player_full_screen_button.clicked.connect(self.on_full_screen_button_click)

        # Create play/pause and volume button images
        self.play_icon = QIcon(QPixmap(get_image_path("play.png")))
        self.pause_icon = QIcon(QPixmap(get_image_path("pause.png")))
        self.stop_icon = QIcon(QPixmap(get_image_path("stop.png")))
        self.volume_on_icon = QIcon(QPixmap(get_image_path("volume_on.png")))
        self.volume_off_icon = QIcon(QPixmap(get_image_path("volume_off.png")))
        self.window().video_player_play_pause_button.setIcon(self.play_icon)
        self.window().video_player_stop_button.setIcon(self.stop_icon)
        self.window().video_player_volume_button.setIcon(self.volume_on_icon)
        self.window().video_player_full_screen_button.setIcon(QIcon(QPixmap(get_image_path("full_screen.png"))))
        self.window().video_player_info_button.setIcon(QIcon(QPixmap(get_image_path("info.png"))))
        self.window().video_player_info_button.hide()

        if sys.platform.startswith('linux'):
            self.mediaplayer.set_xwindow(self.window().video_player_widget.winId())
        elif sys.platform == "win32":
            self.mediaplayer.set_hwnd(self.window().video_player_widget.winId())
        elif sys.platform == "darwin":
            self.mediaplayer.set_nsobject(int(self.window().video_player_widget.winId()))

        self.manager = self.mediaplayer.event_manager()
        self.manager.event_attach(vlc.EventType.MediaPlayerBuffering, self.on_vlc_player_buffering)
        self.manager.event_attach(vlc.EventType.MediaPlayerPlaying, self.on_vlc_player_playing)
        self.manager.event_attach(vlc.EventType.MediaPlayerPositionChanged, self.on_vlc_player_position_changed)

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.on_update_timer_tick)
        self.update_timer.start(500)

        self.window().left_menu_playlist.playing_item_change.connect(self.change_playing_index)
        # now we have a buffering mechanism. so dont initiate the play without buffering
        # self.window().left_menu_playlist.item_should_play.connect(self.on_play_pause_button_click)
        self.window().left_menu_playlist.list_loaded.connect(self.on_files_list_loaded)
        self.window().video_player_play_pause_button.setEnabled(False)
        self.window().video_player_stop_button.setEnabled(False)

    @property
    def needsupdate(self):
        if self.active_infohash != "":
            if not self.isbuffered:
                return True
            try:
                return not self.window().video_player_info_button.popup.isHidden()
            except AttributeError:
                pass
        return False

    @property
    def isbuffered(self):
        return self.prebuf >= 100 and self.footerbuf >= 100 and self.headerbuf >= 100

    def hide_video_widgets(self):
        if self.window().windowState() & Qt.WindowFullScreen:
            self.window().video_player_header_label.setHidden(True)
            self.window().video_player_controls_container.setHidden(True)

    def show_video_widgets(self):
        self.window().video_player_header_label.setHidden(False)
        self.window().video_player_controls_container.setHidden(False)

    def on_update_timer_tick(self):
        if self.freeze:
            return
        total_duration_str = "-:--"
        if self.media and self.media.get_duration() != 0:
            total_duration_str = seconds_to_string(self.media.get_duration() / 1000)

        if self.buffering and self.isbuffered:
            self.buffering = False
            # self.media.parse()
            self.mediaplayer.play()
            self.window().video_player_play_pause_button.setEnabled(True)
            self.window().video_player_stop_button.setEnabled(True)
            self.window().video_player_header_label.setText(self.filename)
        elif self.buffering and not self.isbuffered:
            prebuff = self.prebuf * 0.45 + self.headerbuf * 0.45 + self.footerbuf * 0.1
            self.window().video_player_position_slider.setValue(prebuff * 10)
            self.window().video_player_header_label.setText("Prebuffering %s: %s%%" % (self.filename, int(prebuff)))
        elif self.active_infohash == "" or self.active_index == -1:
            self.window().video_player_position_slider.setValue(0)
            self.window().video_player_time_label.setText("0:00 / -:--")
        else:
            video_time = self.mediaplayer.get_time()
            if video_time == -1:
                video_time = 0

            self.window().video_player_position_slider.setValue(self.mediaplayer.get_position() * 1000)
            self.window().video_player_time_label.setText(
                "%s / %s" % (seconds_to_string(video_time / 1000), total_duration_str)
            )

    def update_prebuf_info(self, download):
        self.prebuf = download.get("vod_prebuffering_progress", 0.0) * 100
        self.headerbuf = download.get("vod_header_progress", 0.0) * 100
        self.footerbuf = download.get("vod_footer_progress", 0.0) * 100
        popup = self.window().video_player_info_button.popup
        for txt, label, value in [
            ("Pre-buffer", popup.prebuf_label, self.prebuf),
            ("Header-buffer", popup.headerbuf_label, self.headerbuf),
            ("Footer-buffer", popup.footerbuf_label, self.footerbuf),
        ]:
            label.setText("<font color='%s'>%s: %2.f%%</font>" % ("orange" if value < 100 else "white", txt, value))

    def update_with_download_info(self, download):
        self.update_prebuf_info(download)
        popup = self.window().video_player_info_button.popup
        popup.download_speed_label.setText(
            "Speed: d %s u %s" % (format_speed(download["speed_down"]), format_speed(download["speed_up"]))
        )
        popup.peers_label.setText("Peers: S%d L%d" % (download["num_seeds"], download["num_peers"]))

    def on_vlc_player_buffering(self, event):
        pass

    def on_vlc_player_playing(self, event):
        pass

    def on_vlc_player_position_changed(self, _):
        self.freeze = False

    def on_should_change_video_time(self, position):
        if not self.mediaplayer or not self.media:
            return

        self.freeze = True
        self.mediaplayer.stop()
        self.mediaplayer.play()
        self.mediaplayer.set_position(position)

        # Guess the current position
        duration = self.media.get_duration() / 1000
        self.window().video_player_time_label.setText(
            f"{seconds_to_string(duration * position)} / " f"{seconds_to_string(duration)}"
        )

    def on_stop_button_click(self):
        if self.stop_media_item():
            self.mediaplayer.stop()
            self.window().video_player_stop_button.setEnabled(False)
            self.window().video_player_play_pause_button.setIcon(self.play_icon)

    def on_play_pause_button_click(self):
        if not self.active_infohash or self.active_index == -1:
            return

        if not self.mediaplayer.is_playing() and not self.buffering:
            self.window().video_player_play_pause_button.setIcon(self.pause_icon)
            self.mediaplayer.play()
            self.window().video_player_stop_button.setEnabled(True)
        else:
            self.window().video_player_play_pause_button.setIcon(self.play_icon)
            self.mediaplayer.pause()

    def on_files_list_loaded(self):
        if self.active_index == -1:
            largest_index, largest_file = self.window().left_menu_playlist.get_largest_file()

            if not largest_file:
                # We don't have a media file in this torrent. Reset everything and show an error
                ConfirmationDialog.show_error(self.window(), "No media files", "This download contains no media files.")
                self.window().hide_left_menu_playlist()
                return

            self.active_index = largest_index
        self.play_active_item()

    def on_volume_button_click(self):
        if not self.mediaplayer.audio_get_mute():
            self.window().video_player_volume_button.setIcon(self.volume_off_icon)
        else:
            self.window().video_player_volume_button.setIcon(self.volume_on_icon)
        self.mediaplayer.audio_toggle_mute()

    def on_volume_change(self):
        self.mediaplayer.audio_set_volume(self.window().video_player_volume_slider.value())

    def on_full_screen_button_click(self):
        if not self.window().windowState() & Qt.WindowFullScreen:
            self.window().top_bar.hide()
            self.window().left_menu.hide()
            self.window().showFullScreen()
        else:
            self.window().exit_full_screen()

    def on_enablestream(self, response):
        self.update_prebuf_info(response)
        self.window().video_player_play_pause_button.setIcon(self.pause_icon)
        if self.isbuffered:
            # self.media.parse()
            self.mediaplayer.play()
            self.window().video_player_play_pause_button.setEnabled(True)
            self.window().video_player_stop_button.setEnabled(True)
        else:
            self.buffering = True
        self.window().video_player_info_button.show()
        self.window().video_player_position_slider.setDisabled(True)

    def play_active_item(self):
        self.window().left_menu_playlist.set_active_index(self.active_index)
        file_info = self.window().left_menu_playlist.get_file_info(self.active_index)
        if file_info is None:
            return
        file_index = file_info["index"]
        self.prebuf = 0.0
        self.footerbuf = 0.0
        self.headerbuf = 0.0
        self.filename = file_info["name"] if file_info else 'Unknown'
        self.window().video_player_header_label.setText(self.filename)
        media_filename = (
            f"http://127.0.0.1:8085/downloads/{self.active_infohash}/stream/"
            f"{file_index}?apikey={self.video_player_api_key}"
        )
        # reset video player controls
        self.mediaplayer.stop()
        self.window().video_player_play_pause_button.setIcon(self.play_icon)
        self.window().video_player_position_slider.setValue(0)
        self.media = self.instance.media_new(media_filename)
        self.mediaplayer.set_media(self.media)
        TriblerNetworkRequest(
            "downloads/%s" % self.active_infohash,
            self.on_enablestream,
            method='PATCH',
            data={"vod_mode": True, "fileindex": file_index},
        )

    def play_media_item(self, infohash, menu_index):
        """
        Play a specific media item in a torrent. If the index is -1, we play the item with the largest size.
        """
        if infohash == self.active_infohash and menu_index == self.active_index:
            return  # We're already playing this item
        if self.mediaplayer.is_playing():
            self.mediaplayer.stop()

        self.active_index = menu_index

        if infohash == self.active_infohash:
            # We changed the index of a torrent that is already playing
            if self.window().left_menu_playlist.loaded_list:
                self.play_active_item()
        else:
            # The download changed, reload the list
            self.window().left_menu_playlist.load_list(infohash)

        self.active_infohash = infohash

    def stop_media_item(self):
        """
        Stop the active streaming in a torrent.
        """
        if self.active_infohash != "" and self.active_index != -1:
            TriblerNetworkRequest(
                "downloads/%s" % self.active_infohash, lambda _: None, method='PATCH', data={"vod_mode": False}
            )
            return True
        return False

    def change_playing_index(self, index):
        self.play_media_item(self.active_infohash, index)

    def reset_player(self):
        """
        Reset the video player, i.e. when a download is removed that was being played.
        """
        if not self.instance:
            return

        self.active_infohash = ""
        self.active_index = -1
        self.window().left_menu_playlist.clear()
        self.window().video_player_header_label.setText("")

        if self.mediaplayer:
            self.mediaplayer.stop()
            self.mediaplayer.set_media(None)
        self.media = None
        self.window().video_player_play_pause_button.setIcon(self.play_icon)
        self.window().video_player_play_pause_button.setEnabled(False)
        self.window().video_player_stop_button.setEnabled(False)
        self.window().video_player_position_slider.setValue(0)
        self.window().video_player_info_button.hide()

    def eventFilter(self, source, event):
        if (
            event.type() == QEvent.KeyRelease
            and self.isVisible()
            and not self.window().top_search_bar.hasFocus()
            and event.key() == Qt.Key_Space
            and self.instance
        ):
            self.on_play_pause_button_click()
        return QWidget.eventFilter(self, source, event)
