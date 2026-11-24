"""
The only module that talks to AWS MediaConvert.
One job per uploaded video: a 720p MP4 (fits a 1280x1280 box, never upscaled)
plus a poster frame, written under the private videos/ prefix.
"""

import boto3
from django.conf import settings

BOX_SIZE = 1280                  # short side 720 for 16:9 and 9:16 video
MP4_MODIFIER = '-720p'
POSTER_MODIFIER = '-poster'
BASE_NAME = 'video'


def get_mediaconvert_client():
    return boto3.client(
        'mediaconvert',
        region_name=settings.AWS_S3_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def output_prefix(asset):
    """videos/YYYY/MM/<asset id>/ (private; the CDN only serves public/)."""
    return f'videos/{asset.created_at:%Y/%m}/{asset.id}/'


def mp4_key(asset):
    return f'{output_prefix(asset)}{BASE_NAME}{MP4_MODIFIER}.mp4'


def poster_keys(asset):
    """Frame at 1 s (preferred), then the first frame (very short clips)."""
    prefix = output_prefix(asset)
    return [
        f'{prefix}{BASE_NAME}{POSTER_MODIFIER}.0000001.jpg',
        f'{prefix}{BASE_NAME}{POSTER_MODIFIER}.0000000.jpg',
    ]


def _job_settings(asset):
    bucket = settings.AWS_S3_BUCKET
    fit_box = {
        'Width': BOX_SIZE,
        'Height': BOX_SIZE,
        'ScalingBehavior': 'FIT_NO_UPSCALE',
    }

    return {
        'TimecodeConfig': {'Source': 'ZEROBASED'},
        'Inputs': [{
            'FileInput': f's3://{bucket}/{asset.storage_key}',
            'TimecodeSource': 'ZEROBASED',
            'VideoSelector': {'Rotate': 'AUTO'},          # phone rotation flags
            'AudioSelectors': {
                'Audio Selector 1': {'DefaultSelection': 'DEFAULT'},
            },
        }],
        'OutputGroups': [{
            'Name': 'File Group',
            'OutputGroupSettings': {
                'Type': 'FILE_GROUP_SETTINGS',
                'FileGroupSettings': {
                    'Destination': f's3://{bucket}/{output_prefix(asset)}{BASE_NAME}',
                },
            },
            'Outputs': [
                # 1) the playable MP4
                {
                    'NameModifier': MP4_MODIFIER,
                    'ContainerSettings': {
                        'Container': 'MP4',
                        # "fast start": playback begins before the file finishes downloading
                        'Mp4Settings': {'MoovPlacement': 'PROGRESSIVE_DOWNLOAD'},
                    },
                    'VideoDescription': {
                        **fit_box,
                        'CodecSettings': {
                            'Codec': 'H_264',
                            'H264Settings': {
                                'RateControlMode': 'QVBR',
                                'QvbrSettings': {'QvbrQualityLevel': 7},
                                'MaxBitrate': 3_000_000,
                                'CodecProfile': 'HIGH',
                                'CodecLevel': 'AUTO',
                                'QualityTuningLevel': 'SINGLE_PASS',
                                'SceneChangeDetect': 'TRANSITION_DETECTION',
                            },
                        },
                    },
                    'AudioDescriptions': [{
                        'AudioSourceName': 'Audio Selector 1',
                        'CodecSettings': {
                            'Codec': 'AAC',
                            'AacSettings': {
                                'Bitrate': 128_000,
                                'CodingMode': 'CODING_MODE_2_0',
                                'SampleRate': 48_000,
                            },
                        },
                    }],
                },
                # 2) poster frames at 0 s and 1 s (we use the 1 s one)
                {
                    'NameModifier': POSTER_MODIFIER,
                    'ContainerSettings': {'Container': 'RAW'},
                    'VideoDescription': {
                        **fit_box,
                        'CodecSettings': {
                            'Codec': 'FRAME_CAPTURE',
                            'FrameCaptureSettings': {
                                'FramerateNumerator': 1,
                                'FramerateDenominator': 1,
                                'MaxCaptures': 2,
                                'Quality': 80,
                            },
                        },
                    },
                },
            ],
        }],
    }


def create_job(asset):
    """Start processing; returns the MediaConvert job id."""
    response = get_mediaconvert_client().create_job(
        Role=settings.MEDIACONVERT_ROLE_ARN,
        Settings=_job_settings(asset),
        UserMetadata={'asset_id': str(asset.id)},
        StatusUpdateInterval='SECONDS_10',
    )
    return response['Job']['Id']


def get_job(job_id):
    return get_mediaconvert_client().get_job(Id=job_id)['Job']