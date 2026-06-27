import type { SVGAttributes } from 'react';

export default function AppLogoIcon(props: SVGAttributes<SVGElement>) {
    return (
        <svg {...props} viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" fill="none">
            <defs>
                <linearGradient id="dryv-gradient" x1="8" y1="8" x2="56" y2="56" gradientUnits="userSpaceOnUse">
                    <stop offset="0" stopColor="currentColor" stopOpacity="0.95" />
                    <stop offset="1" stopColor="currentColor" stopOpacity="0.7" />
                </linearGradient>
            </defs>
            <rect x="14" y="20" width="36" height="28" rx="10" fill="url(#dryv-gradient)" />
            <circle cx="27" cy="34" r="4" fill="white" />
            <circle cx="37" cy="34" r="4" fill="white" />
            <rect x="20" y="42" width="24" height="3" rx="1.5" fill="white" fillOpacity="0.9" />
            <rect x="21" y="8" width="22" height="10" rx="5" fill="url(#dryv-gradient)" />
            <path d="M14 26H8" stroke="url(#dryv-gradient)" strokeWidth="4" strokeLinecap="round" />
            <path d="M56 26H50" stroke="url(#dryv-gradient)" strokeWidth="4" strokeLinecap="round" />
            <circle cx="18" cy="55" r="5" fill="url(#dryv-gradient)" />
            <circle cx="46" cy="55" r="5" fill="url(#dryv-gradient)" />
        </svg>
    );
}
