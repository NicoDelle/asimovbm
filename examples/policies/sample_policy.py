class SampleTransformer:
    def __call__(self, step):
        return {
            "step_id": step.step_id,
            "event_names": [event.name for event in step.task_events],
            "sensor_names": [sensor.name for sensor in step.sensors],
        }


class SamplePolicy:
    def __call__(self, observation):
        return [0.0, 0.0]
