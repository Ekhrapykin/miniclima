from enum import Enum

class Cmd(str, Enum):
    STATUS       = "status"
    VALS         = "vals"
    SERNUM       = "sernum"
    DATE         = "date"
    TIME         = "time"
    OPHOURS      = "ophours"
    DUMP         = "dump"
    SET_SP       = "set-sp"
    SET_LOG_TIME = "set-log-time"
    SET_DATE     = "set-date"
    SET_TIME     = "set-time"
    START        = "start"
    STOP         = "stop"