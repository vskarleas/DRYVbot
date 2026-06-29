<?php

namespace Database\Seeders;

use App\Enums\UserRole;
use App\Models\Medication;
use App\Models\Room;
use App\Models\User;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\Hash;

class DatabaseSeeder extends Seeder
{
    public function run(): void
    {
        User::firstOrCreate(
            ['email' => 'manager@dryvbot.com'],
            [
                'name' => 'Manager',
                'role' => UserRole::Manager,
                'password' => Hash::make('password'),
                'email_verified_at' => now(),
            ]
        );

        User::firstOrCreate(
            ['email' => 'pharmacien@dryvbot.com'],
            [
                'name' => 'Pharmacien',
                'role' => UserRole::Pharmacist,
                'password' => Hash::make('password'),
                'email_verified_at' => now(),
            ]
        );

        $rooms = [
            [
                'name' => 'Salle 101',
                'code' => 'salle_101',
                'x' => -8.1,
                'y' => -6.62,
                'orientation_w' => 0.5199,
                'aliases' => ['room 101', 'salle 101', 'chambre 101'],
            ],
            [
                'name' => 'Salle 102',
                'code' => 'salle_102',
                'x' => -8.904817,
                'y' => -15.881,
                'orientation_w' => 0.5199,
                'aliases' => ['room 102', 'salle 102', 'chambre 102'],
            ],
            [
                'name' => 'Salle 202',
                'code' => 'salle_202',
                'x' => 8.912,
                'y' => -20.42,
                'orientation_w' => 0.5199,
                'aliases' => ['room 202', 'salle 202', 'chambre 202'],
            ],
            [
                'name' => 'Salle 201',
                'code' => 'salle_201',
                'x' => 7.91,
                'y' => -6.77,
                'orientation_w' => 0.5199,
                'aliases' => ['room 201', 'salle 201', 'chambre 201'],
            ],
            [
                'name' => 'Salle Cuisine',
                'code' => 'salle_cuisine',
                'x' => -8.66,
                'y' => -27.77,
                'orientation_w' => 0.5199,
                'aliases' => ['cuisine', 'salle cuisine', 'kitchen'],
            ],
            [
                'name' => 'Salle Reception',
                'code' => 'salle_reception',
                'x' => 2.55,
                'y' => 7.49,
                'orientation_w' => 0.5199,
                'aliases' => ['reception', 'salle reception', 'reception'],
            ],
            [
                'name' => 'Charging Station',
                'code' => 'charging_station',
                'x' => 0.0,
                'y' => 1.95,
                'orientation_w' => 1.0,
                'aliases' => ['charging station', 'station de charge', 'charge station'],
            ],
            [
                'name' => 'Salle Pharmacie',
                'code' => 'salle_pharmacie',
                'x' => -7.96,
                'y' => 14.61,
                'orientation_w' => 0.5199,
                'aliases' => ['pharmacie', 'salle pharmacie', 'pharmacy'],
            ],
        ];

        foreach ($rooms as $room) {
            Room::updateOrCreate(
                ['code' => $room['code']],
                array_merge($room, ['is_active' => true])
            );
        }

        $medications = [
            ['name' => 'Paracetamol 1g', 'code' => 'MED-PARA-1G'],
            ['name' => 'Amoxicilline 500mg', 'code' => 'MED-AMOX-500'],
            ['name' => 'Insuline rapide', 'code' => 'MED-INS-RAP'],
            ['name' => 'Serum physiologique 500ml', 'code' => 'MED-SERUM-500'],
            ['name' => 'Metformine 850mg', 'code' => 'MED-METF-850'],
            ['name' => 'Omeprazole 20mg', 'code' => 'MED-OMEP-20'],
            ['name' => 'Enoxaparine 40mg', 'code' => 'MED-ENOX-40'],
            ['name' => 'Ceftriaxone 1g', 'code' => 'MED-CEF-1G'],
            ['name' => 'Furosemide 40mg', 'code' => 'MED-FURO-40'],
            ['name' => 'Atorvastatine 20mg', 'code' => 'MED-ATOR-20'],
        ];

        foreach ($medications as $medication) {
            Medication::updateOrCreate(
                ['code' => $medication['code']],
                array_merge($medication, ['is_active' => true])
            );
        }
    }
}
