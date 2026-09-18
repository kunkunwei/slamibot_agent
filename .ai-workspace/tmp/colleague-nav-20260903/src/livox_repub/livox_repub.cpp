#include <pcl_conversions/pcl_conversions.h>
#include <sensor_msgs/PointCloud2.h>
#include <tf/transform_listener.h>

#include <algorithm>
#include <cmath>
#include <memory>

#include "livox_ros_driver2/CustomMsg.h"

typedef pcl::PointXYZINormal PointType;
typedef pcl::PointCloud<PointType> PointCloudXYZI;

ros::Publisher pub_pcl_out0, pub_pcl_out1;
uint64_t TO_MERGE_CNT = 1;
constexpr bool b_dbg_line = false;
std::vector<livox_ros_driver2::CustomMsgConstPtr> livox_data;

std::unique_ptr<tf::TransformListener> tf_listener;
bool self_filter_enabled = true;
std::string base_frame = "base_link";
std::string cloud_frame = "laser";
double self_filter_min_x = -0.336;
double self_filter_max_x = 0.336;
double self_filter_min_y = -0.320;
double self_filter_max_y = 0.320;

bool IsInvalidPoint(const livox_ros_driver2::CustomPoint& point) {
  if (!std::isfinite(point.x) || !std::isfinite(point.y) ||
      !std::isfinite(point.z)) {
    return true;
  }

  // Livox may use (0, 0, 0) for an invalid return. Publishing it would
  // become a false obstacle near the lidar after the frame transform.
  constexpr double kMinValidRangeSquared = 1.0e-6;
  return point.x * point.x + point.y * point.y + point.z * point.z <
         kMinValidRangeSquared;
}

bool IsInsideRobotFootprint(const livox_ros_driver2::CustomPoint& point,
                            const tf::StampedTransform& laser_to_base) {
  const tf::Vector3 point_in_base =
      laser_to_base * tf::Vector3(point.x, point.y, point.z);
  return point_in_base.x() >= self_filter_min_x &&
         point_in_base.x() <= self_filter_max_x &&
         point_in_base.y() >= self_filter_min_y &&
         point_in_base.y() <= self_filter_max_y;
}

void LivoxMsgCbk1(const livox_ros_driver2::CustomMsgConstPtr& livox_msg_in) {
  livox_data.push_back(livox_msg_in);
  if (livox_data.size() < TO_MERGE_CNT) return;

  pcl::PointCloud<PointType> pcl_in;

  tf::StampedTransform laser_to_base;
  bool can_filter_footprint = false;
  if (self_filter_enabled) {
    try {
      tf_listener->lookupTransform(base_frame, cloud_frame, ros::Time(0),
                                   laser_to_base);
      can_filter_footprint = true;
    } catch (const tf::TransformException& ex) {
      ROS_WARN_THROTTLE(5.0, "Self-filter waiting for TF %s <- %s: %s",
                        base_frame.c_str(), cloud_frame.c_str(), ex.what());
    }
  }

  size_t invalid_point_count = 0;
  size_t footprint_point_count = 0;

  for (size_t j = 0; j < livox_data.size(); j++) {
    auto& livox_msg = livox_data[j];
    if (livox_msg->points.empty()) continue;

    const auto time_end = livox_msg->points.back().offset_time;
    const size_t point_count =
        std::min(static_cast<size_t>(livox_msg->point_num),
                 livox_msg->points.size());
    for (size_t i = 0; i < point_count; ++i) {
      const auto& source_point = livox_msg->points[i];
      if (IsInvalidPoint(source_point)) {
        ++invalid_point_count;
        continue;
      }
      if (can_filter_footprint &&
          IsInsideRobotFootprint(source_point, laser_to_base)) {
        ++footprint_point_count;
        continue;
      }

      PointType pt;
      pt.x = source_point.x;
      pt.y = source_point.y;
      pt.z = source_point.z;
      const float s = time_end == 0
                          ? 0.0f
                          : source_point.offset_time /
                                static_cast<float>(time_end);

      pt.intensity = source_point.line + source_point.reflectivity / 10000.0;
      pt.curvature = s*0.1;
      pcl_in.push_back(pt);
    }
  }

  ROS_DEBUG_THROTTLE(2.0,
                     "Livox filter removed %zu invalid and %zu footprint points",
                     invalid_point_count, footprint_point_count);

  unsigned long timebase_ns = livox_data[0]->timebase;
  ros::Time timestamp;
  timestamp.fromNSec(timebase_ns);

  sensor_msgs::PointCloud2 pcl_ros_msg;
  pcl::toROSMsg(pcl_in, pcl_ros_msg);
  pcl_ros_msg.header.stamp.fromNSec(timebase_ns);
  pcl_ros_msg.header.frame_id = cloud_frame;
  pub_pcl_out1.publish(pcl_ros_msg);
  livox_data.clear();
}

int main(int argc, char** argv) {
  ros::init(argc, argv, "livox_repub");
  ros::NodeHandle nh;
  ros::NodeHandle private_nh("~");

  private_nh.param("self_filter_enabled", self_filter_enabled, true);
  private_nh.param<std::string>("base_frame", base_frame, "base_link");
  private_nh.param<std::string>("cloud_frame", cloud_frame, "laser");
  private_nh.param("self_filter_min_x", self_filter_min_x, -0.336);
  private_nh.param("self_filter_max_x", self_filter_max_x, 0.336);
  private_nh.param("self_filter_min_y", self_filter_min_y, -0.320);
  private_nh.param("self_filter_max_y", self_filter_max_y, 0.320);

  tf_listener.reset(new tf::TransformListener());

  ROS_INFO("start livox_repub");
  ROS_INFO("Livox self-filter: %s, frame %s -> %s, x=[%.3f, %.3f], y=[%.3f, %.3f]",
           self_filter_enabled ? "enabled" : "disabled", cloud_frame.c_str(),
           base_frame.c_str(), self_filter_min_x, self_filter_max_x,
           self_filter_min_y, self_filter_max_y);

  ros::Subscriber sub_livox_msg1 = nh.subscribe<livox_ros_driver2::CustomMsg>(
      "/livox/lidar", 100, LivoxMsgCbk1);
  pub_pcl_out1 = nh.advertise<sensor_msgs::PointCloud2>("/livox_pcl0", 100);

  ros::spin();
}

