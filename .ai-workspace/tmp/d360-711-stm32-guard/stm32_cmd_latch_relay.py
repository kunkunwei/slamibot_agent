#!/usr/bin/env python3
import rospy
from std_msgs.msg import String


def main():
    rospy.init_node('stm32_cmd_latch_relay')
    publisher = rospy.Publisher('/stm32_cmd_guarded', String, queue_size=1, latch=True)
    rospy.Subscriber('/stm32_cmd', String, publisher.publish, queue_size=1)
    rospy.spin()


if __name__ == '__main__':
    main()
