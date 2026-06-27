<?php

namespace App\Enums;

enum UserRole: string
{
    case Manager = 'manager';
    case Pharmacist = 'pharmacist';

    public function label(): string
    {
        return match ($this) {
            self::Manager => 'Manager',
            self::Pharmacist => 'Pharmacien',
        };
    }
}
