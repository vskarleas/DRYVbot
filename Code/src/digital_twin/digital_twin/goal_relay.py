import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped

class GoalRelay(Node):
    def __init__(self):
        super().__init__('goal_relay')
        self.sub = self.create_subscription(
            PoseStamped,
            '/goal_pose_foxglove',
            self.callback,
            10
        )

        self.pub = self.create_publisher(PoseStamped, '/goal_pose', 10)
        self.get_logger().info('Goal Relay Node has been started.')

    def callback(self, msg):
        msg.header.stamp.sec = 0
        msg.header.stamp.nanosec = 0
        msg.header.frame_id = 'map'
        self.pub.publish(msg)
        self.get_logger().info(f'Received goal pose from Foxglove and published to /goal_pose: {msg.pose}')

def main(args=None):
    rclpy.init(args=args)
    goal_relay_node = GoalRelay()
    rclpy.spin(goal_relay_node)
    goal_relay_node.destroy_node()
    rclpy.shutdown()