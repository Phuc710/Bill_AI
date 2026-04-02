package com.example.myapplication.data.api

import com.example.myapplication.BuildConfig
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitClient {

    private const val BASE_URL = BuildConfig.BASE_URL
    private const val API_KEY = BuildConfig.API_SECRET_KEY

    // Interceptor to attach X-API-Key to every request
    private val authInterceptor = Interceptor { chain ->
        val original = chain.request()
        val requestBuilder = original.newBuilder()
            .header("X-API-Key", API_KEY)
            // Can add more headers here if needed
        
        chain.proceed(requestBuilder.build())
    }

    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY // Good for debugging, disable in Prod release
    }

    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(authInterceptor)
        .addInterceptor(loggingInterceptor)
        .connectTimeout(30, TimeUnit.SECONDS) // Extraction takes time ~ 10-20s
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    private val retrofit: Retrofit by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }

    val apiService: BillApiService by lazy {
        retrofit.create(BillApiService::class.java)
    }

    val supabaseApiService: SupabaseApiService by lazy {
        retrofit.create(SupabaseApiService::class.java)
    }
}
