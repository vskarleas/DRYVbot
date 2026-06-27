<?php

namespace Database\Factories;

use App\Models\Room;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends Factory<Room>
 */
class RoomFactory extends Factory
{
    public function definition(): array
    {
        return [
            'name' => 'Salle ' . fake()->unique()->bothify('??##'),
            'code' => strtoupper(fake()->unique()->bothify('??##')),
            'building' => fake()->optional()->randomElement(['Batiment A', 'Batiment B', 'Batiment C']),
            'floor' => fake()->optional()->randomElement(['RDC', '1er etage', '2eme etage']),
            'description' => fake()->optional()->sentence(),
            'is_active' => true,
        ];
    }
}
