BODY_PARTS = {
    'head': {
        'joints': ['neck'],
        'is_extremity': True,
        'color': 'rgba(255,0,0,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'neck'},
                {'position': [0, -50]}  # Control point at top of head
            ]
        }
    },
    'torso': {
        'joints': ['torso', 'hip', 'left_shoulder', 'right_shoulder'],
        'is_extremity': False,
        'color': 'rgba(0,255,0,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'torso'},
                {'joint': 'hip'},
                {'joint': 'left_shoulder'},
                {'joint': 'right_shoulder'}
            ]
        }
    },
    'left_arm_upper': {
        'joints': ['left_shoulder', 'left_elbow'],
        'is_extremity': False,
        'color': 'rgba(0,0,255,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'left_shoulder'},
                {'joint': 'left_elbow'}
            ]
        }
    },
    'left_arm_lower': {
        'joints': ['left_elbow', 'left_hand'],
        'is_extremity': True,
        'color': 'rgba(255,255,0,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'left_elbow'},
                {'joint': 'left_hand'}
            ]
        }
    },
    'right_arm_upper': {
        'joints': ['right_shoulder', 'right_elbow'],
        'is_extremity': False,
        'color': 'rgba(255,0,255,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'right_shoulder'},
                {'joint': 'right_elbow'}
            ]
        }
    },
    'right_arm_lower': {
        'joints': ['right_elbow', 'right_hand'],
        'is_extremity': True,
        'color': 'rgba(0,255,255,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'right_elbow'},
                {'joint': 'right_hand'}
            ]
        }
    },
    'left_leg_upper': {
        'joints': ['left_hip', 'left_knee'],
        'is_extremity': False,
        'color': 'rgba(128,0,0,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'left_hip'},
                {'joint': 'left_knee'}
            ]
        }
    },
    'left_leg_lower': {
        'joints': ['left_knee', 'left_foot'],
        'is_extremity': True,
        'color': 'rgba(0,128,0,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'left_knee'},
                {'joint': 'left_foot'}
            ]
        }
    },
    'right_leg_upper': {
        'joints': ['right_hip', 'right_knee'],
        'is_extremity': False,
        'color': 'rgba(0,0,128,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'right_hip'},
                {'joint': 'right_knee'}
            ]
        }
    },
    'right_leg_lower': {
        'joints': ['right_knee', 'right_foot'],
        'is_extremity': True,
        'color': 'rgba(128,128,0,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'right_knee'},
                {'joint': 'right_foot'}
            ]
        }
    },
}